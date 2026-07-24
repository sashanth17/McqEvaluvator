from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import os
import shutil
import uuid
from dotenv import load_dotenv
from bson import ObjectId

from app.llms.openRouter import OpenRouterClient
from app.agents.IngestorAgent import process_csv
from app.graph import create_interview_graph
from app.knowledge import initialize_knowledge_state
from gtts import gTTS

def generate_tts(text: str) -> str:
    if not text:
        return None
    try:
        filename = f"{uuid.uuid4()}.mp3"
        filepath = os.path.join("uploads", filename)
        tts = gTTS(text, lang='en')
        tts.save(filepath)
        return f"/uploads/{filename}"
    except Exception as e:
        print(f"TTS Error: {e}")
        return None

interview_app = create_interview_graph()

load_dotenv()

app = FastAPI()

# MongoDB setup
from pymongo import MongoClient
mongo_uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
mongo_client = MongoClient(mongo_uri)
db = mongo_client["mcq_evaluator"]
contexts_collection = db["extracted_contexts"]
interactions_collection = db["interview_interactions"]
reports_collection = db["final_reports"]

# Configure CORS
origins = [
    "http://localhost:5173",  # Vite default port
    "http://127.0.0.1:5173",
    # Add other origins as needed
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("uploads", exist_ok=True)
app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

@app.get("/")
def read_root():
    return {"message": "Welcome to FastAPI Backend"}

@app.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    classification_option: int = Form(1)
):
    if not file:
        raise HTTPException(status_code=400, detail="No file uploaded")
    
    file_path = f"uploads/{file.filename}"
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Process CSV using IngestorAgent
        import asyncio
        import uuid
        thread_id = f"ingest_{uuid.uuid4().hex[:8]}"
        extracted_data = await asyncio.to_thread(process_csv, file_path, classification_option, thread_id)
        
        # Save to MongoDB
        topics = extracted_data.get("topics", [])
        insert_result = contexts_collection.insert_one({
            "filename": file.filename,
            "classification_option": classification_option,
            "topics": topics
        })
        doc_id = str(insert_result.inserted_id)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        file.file.close()
        
    return {
        "message": "File uploaded and processed successfully", 
        "filename": file.filename, 
        "url": f"/uploads/{file.filename}",
        "context_id": doc_id,
        "classification_option": classification_option
    }



class StartInterviewRequest(BaseModel):
    context_id: str

@app.post("/start_interview")
async def start_interview(request: StartInterviewRequest):
    try:
        document = contexts_collection.find_one({"_id": ObjectId(request.context_id)})
        if not document:
            raise HTTPException(status_code=404, detail="Context not found")
        
        topics = document.get("topics", [])
        if not topics:
            raise HTTPException(status_code=400, detail="No topics found in context")
        
        # ── Build all_topics list for multi-topic support ────────────────
        all_topics = []
        for topic_data in topics:
            all_topics.append({
                "topic": topic_data.get("topic", "Unknown"),
                "concepts": topic_data.get("concepts", []),
                "related_mcqs": topic_data.get("questions", []),
                "no_of_questions": topic_data.get("no_of_questions", 0),
                "no_of_crt_ans": topic_data.get("no_of_crt_ans", 0),
            })
        
        # ── Initialize with first topic ──────────────────────────────────
        first_topic = all_topics[0]
        topic_name = first_topic["topic"]
        concepts = first_topic["concepts"]
        related_mcqs = first_topic["related_mcqs"]
        
        # Initialize knowledge state with all concepts set to "unknown"
        initial_ks = initialize_knowledge_state(concepts)
        
        thread_id = str(uuid.uuid4())
        
        initial_state = {
            "thread_id": thread_id,
            
            # Multi-topic
            "all_topics": all_topics,
            "current_topic_index": 0,
            
            # Current topic
            "current_topic": topic_name,
            "concept_map": concepts,
            "related_mcqs": related_mcqs,
            
            # Interview loop
            "interview_history": [],
            "current_question": {},
            "current_intent": {},
            "student_answer": "",
            "current_evaluation": {},
            
            # Knowledge model (THE CENTER)
            "knowledge_state": initial_ks,
            "question_count": 0,
            "information_gain_history": [],
            
            # Session metrics (global across all topics)
            "total_questions_asked": 0,
            "total_answered_correctly": 0,
            
            # Planner
            "planner_directive": {},
            
            # Termination
            "stop_reason": "",
            "report": "",
        }
        
        config = {"configurable": {"thread_id": thread_id}}
        
        import asyncio
        final_state = await asyncio.to_thread(interview_app.invoke, initial_state, config)
        
        audio_url = None
        if final_state.get("current_question"):
            audio_url = generate_tts(final_state["current_question"].get("question", ""))
        
        return {
            "message": "Interview started",
            "thread_id": thread_id,
            "topic": final_state.get("current_topic"),
            "generated_question": final_state.get("current_question"),
            "total_topics": len(all_topics),
            "audio_url": audio_url
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class SubmitAnswerRequest(BaseModel):
    thread_id: str
    student_answer: str
    time_taken_seconds: int = 0

@app.post("/submit_answer")
async def submit_answer(request: SubmitAnswerRequest):
    try:
        config = {"configurable": {"thread_id": request.thread_id}}
        
        import asyncio
        
        def run_graph():
            # Get the question before updating the state
            current_state = interview_app.get_state(config).values
            asked_question = current_state.get("current_question", {})
            
            # Update state with the student's answer and time taken
            interview_app.update_state(config, {
                "student_answer": request.student_answer,
                "time_taken_seconds": request.time_taken_seconds
            })
            # Resume graph (evaluating → routing → planning → questioning → interrupt)
            final_state = interview_app.invoke(None, config)
            
            interactions_collection.insert_one({
                "thread_id": request.thread_id,
                "question": asked_question,
                "student_answer": request.student_answer,
                "evaluation": final_state.get("current_evaluation"),
                "knowledge_state_snapshot": final_state.get("knowledge_state"),
                "question_count": final_state.get("question_count"),
                "current_topic": final_state.get("current_topic"),
                "state_given_to_questioning_agent": current_state,
            })
            
            if final_state.get("report"):
                reports_collection.insert_one({
                    "thread_id": request.thread_id,
                    "report": final_state.get("report"),
                    "knowledge_state": final_state.get("knowledge_state"),
                    "stop_reason": final_state.get("stop_reason"),
                })
            
            return final_state
            
        final_state = await asyncio.to_thread(run_graph)
        
        audio_url = None
        if not final_state.get("report") and final_state.get("current_question"):
            audio_url = generate_tts(final_state["current_question"].get("question", ""))
            
        return {
            "message": "Answer processed",
            "generated_question": final_state.get("current_question"),
            "evaluation": final_state.get("current_evaluation"),
            "report": final_state.get("report"),
            "is_complete": bool(final_state.get("report")),
            "question_count": final_state.get("question_count"),
            "current_topic": final_state.get("current_topic"),
            "stop_reason": final_state.get("stop_reason"),
            "audio_url": audio_url,
            "total_questions_asked": final_state.get("total_questions_asked", 0),
            "total_answered_correctly": final_state.get("total_answered_correctly", 0),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class StopInterviewRequest(BaseModel):
    thread_id: str

@app.post("/stop_interview")
async def stop_interview(request: StopInterviewRequest):
    try:
        config = {"configurable": {"thread_id": request.thread_id}}
        import asyncio
        
        def run_report():
            current_state = interview_app.get_state(config).values
            current_state["stop_reason"] = "manual_stop"
            from app.agents.reportAgent import ReportGeneratorAgent
            report_agent = ReportGeneratorAgent()
            result = report_agent.run(current_state)
            
            # Save report
            if result.get("report"):
                reports_collection.insert_one({
                    "thread_id": request.thread_id,
                    "report": result.get("report"),
                    "knowledge_state": current_state.get("knowledge_state"),
                    "stop_reason": "manual_stop",
                })
            return result.get("report")
            
        report = await asyncio.to_thread(run_report)
        return {"message": "Interview stopped", "report": report}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class ChatRequest(BaseModel):
    prompt: str
    history: list = []

@app.post("/chat")
def chat_endpoint(request: ChatRequest):
    pass

@app.get("/admin/interviews")
def get_all_interviews():
    try:
        # Fetch basic info from final_reports
        reports = list(reports_collection.find({}, {"_id": 0}))
        summaries = []
        for r in reports:
            thread_id = r.get("thread_id")
            report_data = r.get("report", {})
            assessment = report_data.get("assessment_summary", {})
            topic_analysis = report_data.get("topic_analysis", [])
            
            # Extract topic names from all topics in the report
            topic_names = [t.get("topic", "Unknown") for t in topic_analysis] if topic_analysis else ["Unknown"]
            
            summaries.append({
                "thread_id": thread_id,
                "topic": ", ".join(topic_names),
                "overall_understanding": assessment.get("overall_understanding", "Unknown"),
                "summary": assessment.get("summary", ""),
                "stop_reason": r.get("stop_reason", ""),
            })
            
        # Reverse to show newest first
        return {"interviews": summaries[::-1]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/interviews/{thread_id}")
def get_interview_detail(thread_id: str):
    try:
        interactions = list(interactions_collection.find({"thread_id": thread_id}, {"_id": 0}))
        final_report = reports_collection.find_one({"thread_id": thread_id}, {"_id": 0})
        
        return {
            "thread_id": thread_id,
            "interactions": interactions,
            "report": final_report.get("report") if final_report else None,
            "knowledge_state": final_report.get("knowledge_state") if final_report else None,
            "stop_reason": final_report.get("stop_reason") if final_report else None,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/admin/logs")
def get_all_logs():
    try:
        llm_logs_collection = db["llm_logs"]
        logs_cursor = llm_logs_collection.find({}, {"_id": 0}).sort("timestamp", -1).limit(100)
        return {"logs": list(logs_cursor)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
