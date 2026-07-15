"""
Decision Router — Stopping Criteria & Multi-Topic Management

Deterministic logic (no LLM calls) that decides whether to:
1. Continue questioning on the current topic → "planning"
2. Move to the next topic → "load_next_topic"
3. Generate the final report → "reporting"

Stopping Conditions (stop current topic when ANY is true):
- Concept Coverage: ≥ 80% of concepts have evidence_count >= 2
- Overall Confidence: Mean confidence ≥ 0.8
- Diminishing Returns: Last 2 info gains are "low"
- Stable Misconception: Same misconception via ≥ 2 styles
- Uncertainty Resolved: No concept with 0.3 < confidence < 0.7
- Safety Limit: question_count >= MAX_QUESTIONS (default 10)

All thresholds are configurable via environment variables.
"""

import os
from typing import Dict, Any

from app.state import InterviewState
from app.knowledge import (
    compute_concept_coverage,
    compute_overall_confidence,
    check_diminishing_returns,
    get_stable_misconceptions,
    get_uncertain_concepts,
    get_untested_concepts,
    initialize_knowledge_state,
    knowledge_state_summary,
)


# ---------------------------------------------------------------------------
# Configuration (all overridable via environment variables)
# ---------------------------------------------------------------------------

def _get_max_questions() -> int:
    """Per-topic question limit. Strict maximum of 5 questions per topic."""
    try:
        return int(os.environ.get("MAX_QUESTIONS", "5"))
    except ValueError:
        return 5


def _get_coverage_threshold() -> float:
    try:
        return float(os.environ.get("COVERAGE_THRESHOLD", "0.8"))
    except ValueError:
        return 0.8


def _get_confidence_threshold() -> float:
    try:
        return float(os.environ.get("CONFIDENCE_THRESHOLD", "0.8"))
    except ValueError:
        return 0.8


# ---------------------------------------------------------------------------
# Stopping Logic
# ---------------------------------------------------------------------------

def _check_stop_conditions(state: InterviewState) -> str:
    """
    Checks all stopping conditions for the current topic.
    
    Returns:
        Empty string if should continue, or a stop_reason string describing
        which condition triggered the stop.
    """
    # IDK Override: If the evaluator already flagged a topic skip,
    # this acts as an absolute override — bypass all other conditions.
    existing_stop = state.get("stop_reason", "")
    if existing_stop.startswith("topic_skipped_idk"):
        return existing_stop

    ks = state.get("knowledge_state", {"concepts": {}})
    question_count = state.get("question_count", 0)
    info_gain_history = state.get("information_gain_history", [])
    
    # 1. Safety limit (fail-safe — should almost never be the reason)
    max_q = _get_max_questions()
    if question_count >= max_q:
        return f"safety_limit: Reached maximum {max_q} questions."
    
    # Don't check other conditions until at least 2 questions have been asked
    # (need minimum evidence to make meaningful assessments)
    if question_count < 2:
        return ""
    
    # 2. Concept Coverage ≥ threshold
    coverage = compute_concept_coverage(ks)
    coverage_threshold = _get_coverage_threshold()
    if coverage >= coverage_threshold:
        return f"concept_coverage: {coverage:.0%} of concepts have sufficient evidence (threshold: {coverage_threshold:.0%})."
    
    # 3. Overall Confidence ≥ threshold
    confidence = compute_overall_confidence(ks)
    confidence_threshold = _get_confidence_threshold()
    if confidence >= confidence_threshold:
        return f"confidence: Overall confidence {confidence:.2f} ≥ {confidence_threshold} threshold."
    
    # 4. Diminishing Returns
    if check_diminishing_returns(info_gain_history):
        return "diminishing_returns: Last 2 questions produced low information gain."
    
    # 5. Stable Misconception (confirmed through ≥ 2 different styles)
    stable_misc = get_stable_misconceptions(ks)
    if stable_misc:
        concept_names = [name for name, _ in stable_misc]
        return f"stable_misconception: Confirmed misconception(s) in {', '.join(concept_names)} via multiple question styles."
    
    # 6. Uncertainty Resolved (no concept in the high-uncertainty zone)
    uncertain = get_uncertain_concepts(ks)
    untested = get_untested_concepts(ks)
    if not uncertain and not untested and question_count >= 3:
        return "uncertainty_resolved: All concepts have stable beliefs (no high-uncertainty or untested concepts remain)."
    
    return ""


# ---------------------------------------------------------------------------
# Router Node
# ---------------------------------------------------------------------------

def should_continue(state: InterviewState) -> str:
    """
    LangGraph conditional edge function.
    
    Returns:
        "planning"         → Continue questioning (run Assessment Planner next)
        "load_next_topic"  → Current topic done, move to next topic
        "reporting"        → All topics done, generate final report
    """
    stop_reason = _check_stop_conditions(state)
    
    if not stop_reason:
        # Continue questioning this topic
        return "planning"
    
    # Topic is done — check if there are more topics
    all_topics = state.get("all_topics", [])
    current_index = state.get("current_topic_index", 0)
    
    if current_index + 1 < len(all_topics):
        return "load_next_topic"
    else:
        return "reporting"


def route_with_state_update(state: InterviewState) -> Dict[str, Any]:
    """
    LangGraph node that checks stopping conditions and records the reason.
    This runs as a node before the conditional edge.
    
    Returns state updates including stop_reason.
    """
    stop_reason = _check_stop_conditions(state)
    
    updates: Dict[str, Any] = {}
    
    if stop_reason:
        updates["stop_reason"] = stop_reason
        
        # Log the knowledge state summary when a topic stops
        ks = state.get("knowledge_state", {"concepts": {}})
        summary = knowledge_state_summary(ks)
        topic = state.get("current_topic", "Unknown")
        print(f"[Router] Topic '{topic}' stopped: {stop_reason}")
        print(f"[Router] Knowledge State Summary: {summary}")
    
    return updates


# ---------------------------------------------------------------------------
# Load Next Topic Node
# ---------------------------------------------------------------------------

def load_next_topic(state: InterviewState) -> Dict[str, Any]:
    """
    LangGraph node that advances to the next topic.
    
    - Increments current_topic_index
    - Loads the new topic's data into working state
    - Initializes fresh knowledge_state for the new topic's concepts
    - Resets per-topic counters
    
    The frontend is completely unaware this happened — it just
    keeps seeing question/answer pairs.
    """
    all_topics = state.get("all_topics", [])
    current_index = state.get("current_topic_index", 0)
    new_index = current_index + 1
    
    if new_index >= len(all_topics):
        # Shouldn't reach here — should_continue would have routed to "reporting"
        return {"stop_reason": "all_topics_exhausted"}
    
    next_topic = all_topics[new_index]
    topic_name = next_topic.get("topic", "Unknown")
    concepts = next_topic.get("concepts", [])
    related_mcqs = next_topic.get("related_mcqs", next_topic.get("questions", []))
    
    print(f"[Router] Loading next topic: '{topic_name}' (index {new_index}/{len(all_topics) - 1})")
    print(f"[Router] Concepts: {concepts}")
    
    # Initialize fresh knowledge state for the new topic
    new_ks = initialize_knowledge_state(concepts)
    
    return {
        "current_topic_index": new_index,
        "current_topic": topic_name,
        "concept_map": concepts,
        "related_mcqs": related_mcqs,
        "knowledge_state": new_ks,
        "question_count": 0,
        # Note: information_gain_history uses operator.add, but we want a fresh start.
        # We handle this by checking only entries for the current topic in the router.
        "stop_reason": "",
        "planner_directive": {},
        "current_question": {},
        "current_intent": {},
        "current_evaluation": {},
        "student_answer": "",
    }


class DecisionRouter:
    """Wrapper class providing the LangGraph node interface."""
    
    def run(self, state: InterviewState) -> Dict[str, Any]:
        """LangGraph node entry point — records stop reason."""
        return route_with_state_update(state)
