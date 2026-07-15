"""
Interview Graph — Evidence-Driven Knowledge-Model Architecture

Flow:
    START → planning → questioning → [interrupt: wait for answer] → evaluating → routing
                ↑                                                         │
                │                                                         ├─ continue → planning
                │                                                         ├─ next_topic → load_next_topic → planning
                └─────────────────────────────────────────────────────────├─ done → reporting → END

The Knowledge State is the center. Every node reads from and writes to it.
The Assessment Planner (deterministic) selects target evidence.
The Decision Router (deterministic) decides when to stop.
The frontend is unaware of topic transitions.
"""

from langgraph.graph import StateGraph, START, END
from langgraph.checkpoint.memory import MemorySaver

from app.state import InterviewState
from app.agents.questionAgent import QuestioningAgent
from app.agents.evaluvatorAgent import EvaluatorAgent
from app.agents.reportAgent import ReportGeneratorAgent
from app.planner import AssessmentPlanner
from app.router import DecisionRouter, should_continue, load_next_topic


def create_interview_graph():
    graph = StateGraph(InterviewState)

    # Initialize agents and deterministic nodes
    planner = AssessmentPlanner()
    question_agent = QuestioningAgent()
    evaluator_agent = EvaluatorAgent()
    router = DecisionRouter()
    report_agent = ReportGeneratorAgent()

    # Register nodes
    graph.add_node("planning", planner.run)
    graph.add_node("questioning", question_agent.run)
    graph.add_node("evaluating", evaluator_agent.run)
    graph.add_node("routing", router.run)
    graph.add_node("load_next_topic", load_next_topic)
    graph.add_node("reporting", report_agent.run)

    # ── Edges ────────────────────────────────────────────────────────────
    # Entry: start with the Assessment Planner selecting target evidence
    graph.add_edge(START, "planning")

    # Planner → Questioning Agent (transforms directive into a question)
    graph.add_edge("planning", "questioning")

    # Questioning Agent → Evaluating (interrupt here to wait for student answer)
    graph.add_edge("questioning", "evaluating")

    # Evaluating → Routing (router checks stopping conditions)
    graph.add_edge("evaluating", "routing")

    # Router → conditional: continue | next_topic | reporting
    graph.add_conditional_edges("routing", should_continue)

    # Load next topic → back to planning
    graph.add_edge("load_next_topic", "planning")

    # Reporting → END
    graph.add_edge("reporting", END)

    # ── Compile ──────────────────────────────────────────────────────────
    # Interrupt BEFORE evaluating — this is where the system waits for the
    # student's answer. The frontend submits the answer, then the graph
    # resumes from the evaluating node.
    memory = MemorySaver()
    return graph.compile(checkpointer=memory, interrupt_before=["evaluating"])
