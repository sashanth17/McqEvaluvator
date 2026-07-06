from typing import TypedDict, Annotated, List, Dict, Any
import operator
from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from app.agents.questionAgent import QuestioningAgent
from app.agents.evaluvatorAgent import EvaluatorAgent
from app.agents.reportAgent import ReportGeneratorAgent

class InterviewState(TypedDict):
    thread_id: str
    topic: str
    related_questions: List[Dict[str, Any]]
    interview_history: Annotated[List[Dict[str, Any]], operator.add]
    current_question: Dict[str, Any]
    student_answer: str
    current_evaluation: Dict[str, Any]
    report: str

def create_interview_graph():
    graph = StateGraph(InterviewState)
    
    question_agent = QuestioningAgent()
    evaluator_agent = EvaluatorAgent()
    report_agent = ReportGeneratorAgent()
    
    graph.add_node("questioning", question_agent.run)
    graph.add_node("evaluating", evaluator_agent.run)
    graph.add_node("reporting", report_agent.run)
    
    graph.add_edge(START, "questioning")
    graph.add_edge("questioning", "evaluating")
    graph.add_edge("evaluating", "questioning") # Loop back for next question (we can add conditional edges later)
    # For now, let's keep it simple: questioning -> interrupt -> evaluating -> back to questioning. 
    # To end the interview, we can have a max_questions logic. Let's add a conditional edge.
    
    def should_continue(state: InterviewState):
        # Stop exactly after 5 questions have been asked and evaluated
        history = state.get("interview_history", [])
        if len(history) >= 5:
            return "reporting"
        return "questioning"
        
    graph.add_conditional_edges("evaluating", should_continue)
    graph.add_edge("reporting", END)
    
    memory = MemorySaver()
    return graph.compile(checkpointer=memory, interrupt_before=["evaluating"])
