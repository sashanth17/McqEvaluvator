"""
Knowledge State Utilities — Pure deterministic functions (no LLM calls).

These functions operate on the KnowledgeState and are used by the
Assessment Planner, Decision Router, and Evaluator Agent.

All functions are side-effect-free and testable.
"""

from typing import List, Dict, Any, Optional, Tuple
import copy

from app.state import KnowledgeState, ConceptBelief, EvidenceEntry


# ---------------------------------------------------------------------------
# Initialization
# ---------------------------------------------------------------------------

def initialize_knowledge_state(concepts: List[str]) -> KnowledgeState:
    """
    Creates the initial KnowledgeState with all concepts set to 'unknown'.
    
    Args:
        concepts: List of concept names extracted from MCQs for one topic.
        
    Returns:
        A KnowledgeState with every concept in the 'unknown' state.
    """
    concept_beliefs: Dict[str, ConceptBelief] = {}
    for concept in concepts:
        concept_beliefs[concept] = {
            "belief": "unknown",
            "confidence": 0.05,
            "evidence_count": 0,
            "evidence": [],
            "question_styles_used": [],
            "misconceptions": [],
            "last_updated_turn": 0,
            "information_gain": ""
        }
    return {"concepts": concept_beliefs}


# ---------------------------------------------------------------------------
# Coverage & Confidence Metrics
# ---------------------------------------------------------------------------

def compute_concept_coverage(ks: KnowledgeState) -> float:
    """
    Fraction of concepts with sufficient evidence (evidence_count >= 2).
    
    Returns 0.0 if no concepts exist.
    """
    concepts = ks.get("concepts", {})
    if not concepts:
        return 0.0
    
    sufficient = sum(
        1 for c in concepts.values()
        if c.get("evidence_count", 0) >= 2
    )
    return sufficient / len(concepts)


def compute_overall_confidence(ks: KnowledgeState) -> float:
    """
    Mean confidence across all concepts.
    
    Returns 0.0 if no concepts exist.
    """
    concepts = ks.get("concepts", {})
    if not concepts:
        return 0.0
    
    total = sum(c.get("confidence", 0.0) for c in concepts.values())
    return total / len(concepts)


# ---------------------------------------------------------------------------
# Concept Queries
# ---------------------------------------------------------------------------

def get_untested_concepts(ks: KnowledgeState) -> List[str]:
    """Returns concept names with belief == 'unknown'."""
    return [
        name for name, state in ks.get("concepts", {}).items()
        if state.get("belief", "unknown") == "unknown"
    ]


def get_uncertain_concepts(ks: KnowledgeState) -> List[str]:
    """
    Returns concept names in the high-uncertainty zone (0.3 < confidence < 0.7).
    These concepts have some evidence but the belief is not yet stable.
    """
    return [
        name for name, state in ks.get("concepts", {}).items()
        if 0.3 < state.get("confidence", 0.0) < 0.7
    ]


def get_misconceptions(ks: KnowledgeState) -> List[str]:
    """Returns concept names that have belief == 'misconception' or have misconception entries."""
    results = []
    for name, state in ks.get("concepts", {}).items():
        if state.get("belief") == "misconception":
            results.append(name)
        elif state.get("misconceptions"):
            results.append(name)
    return list(set(results))


def get_stable_misconceptions(ks: KnowledgeState) -> List[Tuple[str, List[str]]]:
    """
    Returns misconceptions confirmed through >= 2 different question styles.
    
    A stable misconception means the same wrong understanding has been
    observed from multiple angles — further questioning is unlikely to help.
    
    Returns:
        List of (concept_name, [misconception_texts]) tuples.
    """
    stable = []
    for name, state in ks.get("concepts", {}).items():
        misconceptions = state.get("misconceptions", [])
        styles_used = state.get("question_styles_used", [])
        
        if misconceptions and len(set(styles_used)) >= 2:
            # Misconception persists across multiple question styles
            if state.get("belief") == "misconception":
                stable.append((name, misconceptions))
    
    return stable


def get_highest_uncertainty_concept(ks: KnowledgeState) -> Optional[str]:
    """
    Returns the concept with confidence closest to 0.5 (maximum uncertainty).
    
    This is the concept where one more question would provide the most 
    information gain, from a pure uncertainty-reduction perspective.
    
    Returns None if no concepts exist.
    """
    concepts = ks.get("concepts", {})
    if not concepts:
        return None
    
    # Sort by distance from 0.5 (ascending = most uncertain first)
    sorted_concepts = sorted(
        concepts.items(),
        key=lambda item: abs(item[1].get("confidence", 0.0) - 0.5)
    )
    
    return sorted_concepts[0][0] if sorted_concepts else None


def get_concepts_needing_corroboration(ks: KnowledgeState) -> List[str]:
    """
    Returns concepts with exactly 1 evidence entry — they need a second
    data point to corroborate or challenge the initial assessment.
    """
    return [
        name for name, state in ks.get("concepts", {}).items()
        if state.get("evidence_count", 0) == 1
    ]


def get_low_confidence_concepts(ks: KnowledgeState) -> List[str]:
    """Returns concepts with confidence < 0.3 that are not 'unknown'."""
    return [
        name for name, state in ks.get("concepts", {}).items()
        if state.get("confidence", 0.0) < 0.3
        and state.get("belief", "unknown") != "unknown"
    ]


# ---------------------------------------------------------------------------
# Diminishing Returns Detection
# ---------------------------------------------------------------------------

def check_diminishing_returns(info_gain_history: List[Dict[str, Any]]) -> bool:
    """
    Returns True if the last 2 consecutive entries have information_gain == 'low'.
    
    This indicates that further questioning is unlikely to produce new evidence.
    """
    if len(info_gain_history) < 2:
        return False
    
    last_two = info_gain_history[-2:]
    return all(
        entry.get("information_gain", "").lower() == "low"
        for entry in last_two
    )


# ---------------------------------------------------------------------------
# Knowledge State Updates
# ---------------------------------------------------------------------------

def merge_concept_update(
    ks: KnowledgeState,
    concept_name: str,
    update: ConceptBelief,
    turn: int
) -> KnowledgeState:
    """
    Immutably merges an evaluator's concept update into the existing KnowledgeState.
    
    The update from the evaluator is merged into the existing concept entry:
    - evidence entries are appended (not replaced)
    - question_styles_used are merged (deduplicated)
    - misconceptions are merged (deduplicated)
    - belief, confidence, evidence_count, last_updated_turn, information_gain are overwritten
    
    Args:
        ks: Current KnowledgeState.
        concept_name: The concept being updated.
        update: New ConceptBelief from the evaluator.
        turn: Current question number.
        
    Returns:
        A new KnowledgeState with the update merged.
    """
    new_ks = copy.deepcopy(ks)
    concepts = new_ks.get("concepts", {})
    
    existing = concepts.get(concept_name, {
        "belief": "unknown",
        "confidence": 0.05,
        "evidence_count": 0,
        "evidence": [],
        "question_styles_used": [],
        "misconceptions": [],
        "last_updated_turn": 0,
        "information_gain": ""
    })
    
    # Append new evidence entries
    new_evidence = update.get("evidence", [])
    existing_evidence = existing.get("evidence", [])
    merged_evidence = existing_evidence + new_evidence
    
    # Merge question styles (deduplicate, preserve order)
    existing_styles = existing.get("question_styles_used", [])
    new_styles = update.get("question_styles_used", [])
    seen = set(existing_styles)
    merged_styles = list(existing_styles)
    for s in new_styles:
        if s not in seen:
            merged_styles.append(s)
            seen.add(s)
    
    # Merge misconceptions (deduplicate)
    existing_misconceptions = existing.get("misconceptions", [])
    new_misconceptions = update.get("misconceptions", [])
    merged_misconceptions = list(set(existing_misconceptions + new_misconceptions))
    
    # Overwrite scalar fields
    existing["belief"] = update.get("belief", existing.get("belief", "unknown"))
    existing["confidence"] = update.get("confidence", existing.get("confidence", 0.05))
    existing["evidence_count"] = len(merged_evidence)
    existing["evidence"] = merged_evidence
    existing["question_styles_used"] = merged_styles
    existing["misconceptions"] = merged_misconceptions
    existing["last_updated_turn"] = turn
    existing["information_gain"] = update.get("information_gain", "")
    
    concepts[concept_name] = existing
    new_ks["concepts"] = concepts
    
    return new_ks


def get_styles_used_for_concept(ks: KnowledgeState, concept_name: str) -> List[str]:
    """Returns the list of question styles already used for a specific concept."""
    concepts = ks.get("concepts", {})
    concept = concepts.get(concept_name, {})
    return concept.get("question_styles_used", [])


# ---------------------------------------------------------------------------
# Summary helpers (for display / debugging)
# ---------------------------------------------------------------------------

def knowledge_state_summary(ks: KnowledgeState) -> Dict[str, Any]:
    """
    Returns a compact summary of the knowledge state for logging/debugging.
    """
    concepts = ks.get("concepts", {})
    return {
        "total_concepts": len(concepts),
        "coverage": round(compute_concept_coverage(ks), 2),
        "overall_confidence": round(compute_overall_confidence(ks), 2),
        "untested": get_untested_concepts(ks),
        "uncertain": get_uncertain_concepts(ks),
        "misconceptions": get_misconceptions(ks),
        "beliefs": {
            name: {
                "belief": state.get("belief", "unknown"),
                "confidence": round(state.get("confidence", 0.0), 2),
                "evidence_count": state.get("evidence_count", 0)
            }
            for name, state in concepts.items()
        }
    }
