"""
Assessment Planner — Deterministic Target Evidence Selection

NOT an LLM agent. Pure deterministic logic that answers:
1. Which concepts remain untested?
2. Which concepts have conflicting evidence?
3. Which misconceptions are stable?
4. Which concept offers the highest expected information gain?

The planner selects the target evidence and passes a directive to the
Questioning Agent, which merely transforms it into a natural question.

This separation makes the system more predictable and easier to debug.
"""

from typing import Dict, Any, List, Optional

from app.state import InterviewState, KnowledgeState
from app.knowledge import (
    get_untested_concepts,
    get_uncertain_concepts,
    get_misconceptions,
    get_stable_misconceptions,
    get_highest_uncertainty_concept,
    get_concepts_needing_corroboration,
    get_low_confidence_concepts,
    get_styles_used_for_concept,
)

# Maximum number of recent history entries per concept sent to QuestioningAgent
_HISTORY_WINDOW = 2


# The 8 approved question styles
QUESTION_STYLES = [
    "explanation",
    "comparison",
    "application",
    "debugging",
    "counterexample",
    "trade_off",
    "scenario",
    "design",
]


def _select_style(ks: KnowledgeState, concept: str) -> str:
    """
    Select the next question style for a concept, avoiding recently used styles.
    
    Priority:
    1. Styles never used for this concept
    2. If all styles used, pick the least-recently-used one
    """
    used_styles = get_styles_used_for_concept(ks, concept)
    
    # Find styles not yet used for this concept
    unused = [s for s in QUESTION_STYLES if s not in used_styles]
    
    if unused:
        return unused[0]
    
    # All styles used — cycle through from the beginning
    # (least-recently-used is first in the original order that isn't last used)
    if used_styles:
        last_used = used_styles[-1]
        for s in QUESTION_STYLES:
            if s != last_used:
                return s
    
    return QUESTION_STYLES[0]


def _build_focus_context(ks: KnowledgeState, concept: str, related_mcqs: List[Dict[str, Any]]) -> str:
    """
    Build a concise focus_context string for the planner_directive.

    Covers:
    - Belief state summary (including active misconceptions)
    - Last evaluator observation for this concept
    - Cold-start MCQ note (if no evidence exists yet)
    """
    concepts = ks.get("concepts", {})
    state = concepts.get(concept, {})

    evidence = state.get("evidence", [])
    misconceptions = state.get("misconceptions", [])
    belief = state.get("belief", "unknown")

    notes = []

    if belief == "unknown":
        # Cold start — derive calibration hint from MCQ performance
        concept_lower = concept.lower()
        relevant_mcqs = [
            q for q in related_mcqs
            if concept_lower in q.get("question", "").lower()
        ]
        if relevant_mcqs:
            correct = sum(1 for q in relevant_mcqs if q.get("is_correct", False))
            total = len(relevant_mcqs)
            pct = int(correct / total * 100)
            notes.append(
                f"No prior interview evidence. MCQ performance on related questions: "
                f"{correct}/{total} correct ({pct}%). "
                f"{'Verify understanding, not just recall.' if pct >= 50 else 'Likely misconception or gap — probe carefully.'}"
            )
        else:
            notes.append("No prior evidence exists for this concept. Start with an open-ended exploration.")
    elif belief == "emerging":
        notes.append("Initial evidence is weak. Need a clearer signal on this concept.")
    elif belief == "partial":
        notes.append("Student shows partial understanding. Probe for specific gaps.")
    elif belief == "strong":
        notes.append("Student shows strong understanding. Challenge with edge cases or trade-offs.")
    elif belief == "mastered":
        notes.append("Student has demonstrated mastery. Consider moving on.")
    elif belief == "misconception":
        notes.append(f"Active misconception detected: {'; '.join(misconceptions)}. Use a different style to surface it.")

    # Append the most recent evaluator observation for this concept
    if evidence:
        last = evidence[-1]
        notes.append(
            f"Last observation (style: {last.get('question_style', '?')}): "
            f"{last.get('observation', 'N/A')}"
        )

    return " ".join(notes) if notes else ""


def _build_recent_concept_history(
    interview_history: List[Dict[str, Any]],
    concept: str,
) -> List[Dict[str, str]]:
    """
    Extract the last _HISTORY_WINDOW Q&A entries from interview_history that
    targeted this specific concept, compressed to the fields the QuestioningAgent needs.

    Returns a list of dicts:
        [
          {
            "question": "...",
            "student_answer": "...",
            "evaluator_observation": "..."
          },
          ...
        ]
    """
    matching = [
        entry for entry in interview_history
        if entry.get("target_concept", "") == concept
    ]
    # Take last _HISTORY_WINDOW entries
    recent = matching[-_HISTORY_WINDOW:]

    compressed = []
    for entry in recent:
        evaluation = entry.get("evaluation", {})
        # Prefer feedback_summary; fall back to expected_vs_observed.observed
        observation = (
            evaluation.get("feedback_summary")
            or evaluation.get("expected_vs_observed", {}).get("observed", "")
            or ""
        )
        compressed.append({
            "question": entry.get("question", ""),
            "student_answer": entry.get("student_answer", ""),
            "evaluator_observation": observation,
        })

    return compressed


def plan_next_assessment(state: InterviewState) -> Dict[str, Any]:
    """
    Deterministic assessment planner. Selects the highest-value target
    evidence and produces a directive for the Questioning Agent.
    
    This runs as a LangGraph node, writing its output to state["planner_directive"].
    
    Selection Priority:
    1. Concepts with active misconceptions (need confirmation via different style)
    2. Concepts with high uncertainty (confidence near 0.5)
    3. Untested concepts
    4. Concepts needing corroboration (only 1 evidence entry)
    5. Low-confidence concepts (< 0.3, not unknown)
    
    Returns:
        State update with planner_directive containing:
        - target_concept: str
        - reason: str  
        - suggested_style: str
        - styles_to_avoid: List[str]
        - context: str (prior evidence summary)
    """
    ks = state.get("knowledge_state", {"concepts": {}})
    interview_history = state.get("interview_history", [])
    related_mcqs = state.get("related_mcqs", [])
    
    target_concept = None
    reason = ""
    
    # --- Priority 1: Active misconceptions ---
    misconception_concepts = get_misconceptions(ks)
    stable = {name for name, _ in get_stable_misconceptions(ks)}
    
    # Only pursue unstable misconceptions (stable ones are confirmed, stop investigating)
    active_misconceptions = [c for c in misconception_concepts if c not in stable]
    
    if active_misconceptions:
        target_concept = active_misconceptions[0]
        concept_state = ks.get("concepts", {}).get(target_concept, {})
        reason = (
            f"Active misconception detected (belief: misconception, confidence: "
            f"{concept_state.get('confidence', 0.0):.2f}). "
            f"Need confirmation via different question style."
        )
    
    # --- Priority 2: High uncertainty (confidence near 0.5) ---
    if target_concept is None:
        uncertain = get_uncertain_concepts(ks)
        if uncertain:
            # Pick the one closest to 0.5
            concepts_data = ks.get("concepts", {})
            uncertain.sort(key=lambda c: abs(concepts_data.get(c, {}).get("confidence", 0.0) - 0.5))
            target_concept = uncertain[0]
            conf = concepts_data.get(target_concept, {}).get("confidence", 0.0)
            reason = f"High uncertainty (confidence: {conf:.2f}). One more question could resolve the belief."
    
    # --- Priority 3: Untested concepts ---
    if target_concept is None:
        untested = get_untested_concepts(ks)
        if untested:
            target_concept = untested[0]
            reason = "Concept is untested. No evidence collected yet."
    
    # --- Priority 4: Concepts needing corroboration ---
    if target_concept is None:
        needing = get_concepts_needing_corroboration(ks)
        if needing:
            target_concept = needing[0]
            reason = "Only 1 evidence entry. Need a second data point to corroborate or challenge."
    
    # --- Priority 5: Low-confidence concepts ---
    if target_concept is None:
        low_conf = get_low_confidence_concepts(ks)
        if low_conf:
            target_concept = low_conf[0]
            concept_state = ks.get("concepts", {}).get(target_concept, {})
            reason = (
                f"Low confidence ({concept_state.get('confidence', 0.0):.2f}) "
                f"despite some evidence. Need deeper investigation."
            )
    
    # --- Fallback: pick highest uncertainty concept ---
    if target_concept is None:
        target_concept = get_highest_uncertainty_concept(ks)
        if target_concept:
            reason = "All concepts have some evidence. Targeting highest remaining uncertainty."
        else:
            # Edge case: no concepts at all (shouldn't happen)
            target_concept = "General Understanding"
            reason = "No specific concepts available. Assessing general understanding."
    
    # Select question style
    suggested_style = _select_style(ks, target_concept)
    styles_to_avoid = get_styles_used_for_concept(ks, target_concept)
    
    # Build lean context fields for the QuestioningAgent
    focus_context = _build_focus_context(ks, target_concept, related_mcqs)
    recent_concept_history = _build_recent_concept_history(interview_history, target_concept)

    directive = {
        "target_concept": target_concept,
        "reason": reason,
        "suggested_style": suggested_style,
        "styles_to_avoid": styles_to_avoid,
        "focus_context": focus_context,
        "recent_concept_history": recent_concept_history,
    }

    return {"planner_directive": directive}


class AssessmentPlanner:
    """Wrapper class for the LangGraph node interface."""
    
    def run(self, state: InterviewState) -> Dict[str, Any]:
        """LangGraph node entry point."""
        return plan_next_assessment(state)
