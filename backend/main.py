from importlib import readers
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import os
import shutil
from dotenv import load_dotenv
from bson import ObjectId
from pydantic import BaseModel

from app.llms.openRouter import OpenRouterClient
from app.agents.IngestorAgent import process_csv
from app.graph import create_interview_graph

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
async def upload_file(file: UploadFile = File(...)):
    if not file:
        raise HTTPException(status_code=400, detail="No file uploaded")
    
    file_path = f"uploads/{file.filename}"
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
            
        # Process CSV using IngestorAgent
        import asyncio
        extracted_data = await asyncio.to_thread(process_csv, file_path)
        
        # Save to MongoDB
        topics = extracted_data.get("topics", [])
        insert_result = contexts_collection.insert_one({
            "filename": file.filename,
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
        "context_id": doc_id
    }

@app.post("/ingest")
def ingest_content():
    return {"message": "Content ingested successfully"} 

import uuid

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
            
        first_topic_data = topics[0]
        topic_name = first_topic_data.get("topic", "Unknown")
        related_questions = first_topic_data.get("questions", [])
        
        thread_id = str(uuid.uuid4())
        
        initial_state = {
            "thread_id": thread_id,
            "topic": topic_name,
            "related_questions": related_questions,
            "interview_history": [],
            "current_question": {},
            "student_answer": "",
            "current_evaluation": {},
            "report": ""
        }
        
        config = {"configurable": {"thread_id": thread_id}}
        
        import asyncio
        final_state = await asyncio.to_thread(interview_app.invoke, initial_state, config)
        
        return {
            "message": "Interview started",
            "thread_id": thread_id,
            "topic": final_state.get("topic"),
            "generated_question": final_state.get("current_question")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class SubmitAnswerRequest(BaseModel):
    thread_id: str
    student_answer: str

@app.post("/submit_answer")
async def submit_answer(request: SubmitAnswerRequest):
    try:
        config = {"configurable": {"thread_id": request.thread_id}}
        
        # We resume by updating the state with the answer, then invoking the graph
        # Since it paused before "evaluating", we can update the state and invoke with None
        import asyncio
        
        def run_graph():
            # Get the question before updating the state
            current_state = interview_app.get_state(config).values
            asked_question = current_state.get("current_question", {})
            
            # Update state with the student's answer
            interview_app.update_state(config, {"student_answer": request.student_answer})
            # Resume graph
            final_state = interview_app.invoke(None, config)
            
            interactions_collection.insert_one({
                "thread_id": request.thread_id,
                "question": asked_question,
                "student_answer": request.student_answer,
                "evaluation": final_state.get("current_evaluation"),
                "state_given_to_questioning_agent": current_state
            })
            
            if final_state.get("report"):
                reports_collection.insert_one({
                    "thread_id": request.thread_id,
                    "report": final_state.get("report")
                })
            
            return final_state
            
        final_state = await asyncio.to_thread(run_graph)
        
        return {
            "message": "Answer processed",
            "generated_question": final_state.get("current_question"),
            "evaluation": final_state.get("current_evaluation"),
            "report": final_state.get("report"),
            "is_complete": bool(final_state.get("report"))
        }
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
        # We can extract summary info to send to the frontend
        summaries = []
        for r in reports:
            thread_id = r.get("thread_id")
            report_data = r.get("report", {})
            assessment = report_data.get("assessment_summary", {})
            topic = report_data.get("topic_analysis", [{}])[0].get("topic", "Unknown") if report_data.get("topic_analysis") else "Unknown"
            
            summaries.append({
                "thread_id": thread_id,
                "topic": topic,
                "overall_understanding": assessment.get("overall_understanding", "Unknown"),
                "summary": assessment.get("summary", "")
            })
            
        # Reverse to show newest first if we assume order of insertion
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
            "report": final_report.get("report") if final_report else None
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
