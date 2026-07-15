"""
State definitions for the Evidence-Driven Knowledge-Model Architecture.

The KnowledgeState is the center of the system. Every agent reads from and writes to it.
The assessment follows a scientific loop:
    Hypothesis → Question → Answer → Evidence → Belief Update
"""

from typing import TypedDict, Annotated, List, Dict, Any, Optional
import operator


# ---------------------------------------------------------------------------
# Evidence & Belief Model
# ---------------------------------------------------------------------------

class EvidenceEntry(TypedDict, total=False):
    """A single piece of evidence collected from a student's answer."""
    question_style: str      # "explanation" | "comparison" | "application" | "debugging" |
                             # "counterexample" | "trade_off" | "scenario" | "design"
    observation: str         # e.g. "Understands residual capacity but confuses reverse edges."
    turn: int                # Which question number produced this evidence


class ConceptBelief(TypedDict, total=False):
    """
    Evidence-based belief about a student's understanding of a single concept.
    
    Belief progression: unknown → emerging → partial → strong → mastered
    Special state: misconception (can coexist with any confidence level)
    
    Agents reason in terms of belief labels. The confidence float (0.0–1.0)
    is for internal use by the Router and Planner.
    """
    belief: str               # "unknown" | "emerging" | "partial" | "strong" | "mastered" | "misconception"
    confidence: float         # 0.0 – 1.0 (internal; agents use belief labels)
    evidence_count: int
    evidence: List[EvidenceEntry]
    question_styles_used: List[str]
    misconceptions: List[str]
    last_updated_turn: int
    information_gain: str     # "high" | "medium" | "low" (from the last update to this concept)


class KnowledgeState(TypedDict, total=False):
    """
    Structured map of the student's understanding for the current topic.
    
    Example:
        {
            "concepts": {
                "Shortest Path Property": {
                    "belief": "strong",
                    "confidence": 0.88,
                    "evidence_count": 2,
                    "evidence": [
                        {"question_style": "explanation", "observation": "...", "turn": 1},
                        {"question_style": "counterexample", "observation": "...", "turn": 3}
                    ],
                    "question_styles_used": ["explanation", "counterexample"],
                    "misconceptions": [],
                    "last_updated_turn": 3,
                    "information_gain": "high"
                },
                "Residual Graph": {
                    "belief": "partial",
                    "confidence": 0.52,
                    "evidence": [...],
                    ...
                }
            }
        }
    """
    concepts: Dict[str, ConceptBelief]


# ---------------------------------------------------------------------------
# Question Intent (Hypothesis-Driven Questioning)
# ---------------------------------------------------------------------------

class QuestionIntent(TypedDict, total=False):
    """
    Every generated question carries an intent — making the assessment scientific.
    
    The Evaluator compares expected_evidence vs what the student actually demonstrated.
    """
    target_concept: str       # "Residual Graph"
    hypothesis: str           # "Student may understand residual capacity but not reverse edges."
    expected_evidence: str    # "If they explain reverse edge creation correctly, confidence increases."


# ---------------------------------------------------------------------------
# Information Gain Report
# ---------------------------------------------------------------------------

class InformationGainReport(TypedDict, total=False):
    """
    Structured output from the Evaluator describing what new information was gained.
    The Router uses this for diminishing-returns detection.
    """
    new_concepts: int           # Concepts that moved from "unknown" to something else
    updated_concepts: int       # Concepts whose belief/confidence changed
    misconceptions_found: int   # New misconceptions detected
    information_gain: str       # "high" | "medium" | "low"
    reason: str                 # WHY this gain level — for debugging and transparency


# ---------------------------------------------------------------------------
# Topic Data
# ---------------------------------------------------------------------------

class TopicData(TypedDict, total=False):
    """A single topic extracted by the Ingestor, with its concepts and MCQs."""
    topic: str
    concepts: List[str]
    related_mcqs: List[Dict[str, Any]]
    no_of_questions: int
    no_of_crt_ans: int


# ---------------------------------------------------------------------------
# Interview State (THE GRAPH STATE)
# ---------------------------------------------------------------------------

class InterviewState(TypedDict):
    """
    The complete state of an assessment interview.
    
    The knowledge_state is the CENTER of the system.
    Every agent reads from and writes to it.
    
    Multi-topic: The Router increments current_topic_index when a topic is
    finished, loads the next topic's data, and resets the per-topic state.
    The frontend is unaware of topic transitions — it only sees Q&A.
    """
    thread_id: str

    # ── Multi-topic support ──────────────────────────────────────────────
    all_topics: List[TopicData]
    current_topic_index: int

    # ── Current topic working state ──────────────────────────────────────
    current_topic: str
    concept_map: List[str]                   # Concepts extracted from MCQs for this topic
    related_mcqs: List[Dict[str, Any]]

    # ── Interview loop ───────────────────────────────────────────────────
    interview_history: Annotated[List[Dict[str, Any]], operator.add]
    current_question: Dict[str, Any]
    current_intent: QuestionIntent
    student_answer: str
    current_evaluation: Dict[str, Any]

    # ── Knowledge model (THE CENTER) ─────────────────────────────────────
    knowledge_state: KnowledgeState
    question_count: int
    information_gain_history: Annotated[List[Dict[str, Any]], operator.add]

    # ── Assessment Planner output (fed to Questioning Agent) ─────────────
    planner_directive: Dict[str, Any]

    # ── Session Metrics (global across all topics) ─────────────────────
    total_questions_asked: int
    total_answered_correctly: int
    time_taken_seconds: int

    # ── Termination ──────────────────────────────────────────────────────
    stop_reason: str
    report: str
