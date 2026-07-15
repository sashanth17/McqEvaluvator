import os
import json
import sys
import time
import re
from typing import List, Dict, Any

from app.llms.factory import get_llm_client


class ReportGeneratorAgent:
    def __init__(self, model: str = None):
        self.client = get_llm_client()

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generates the final assessment report from the Knowledge State.
        
        The Knowledge State is the TRUTH. Interview history is used
        only for supporting quotes.
        
        For multi-topic interviews, all topics and their knowledge states
        are included in the report.
        """
        all_topics = state.get("all_topics", [])
        interview_history = state.get("interview_history", [])
        knowledge_state = state.get("knowledge_state", {"concepts": {}})
        current_topic = state.get("current_topic", "Unknown Topic")
        
        # Build per-topic data for the report
        # For a multi-topic interview, we need to reconstruct per-topic history
        # The knowledge_state in the final state is for the LAST topic
        # For previous topics, we extract from interview_history
        
        topics_data = []
        
        if len(all_topics) <= 1:
            # Single topic — straightforward
            topic_name = current_topic
            related_mcqs = state.get("related_mcqs", [])
            stop_reason = state.get("stop_reason", "")
            question_count = state.get("question_count", 0)
            
            topics_data.append({
                "topic": topic_name,
                "knowledge_state": knowledge_state,
                "related_mcqs": related_mcqs,
                "interview_history": interview_history,
                "stop_reason": stop_reason,
                "question_count": question_count,
            })
        else:
            # Multi-topic — group history by topic
            # Each history entry has a target_concept which links to a topic
            # We reconstruct topic-specific histories
            for idx, topic_data in enumerate(all_topics):
                topic_name = topic_data.get("topic", "Unknown")
                related_mcqs = topic_data.get("related_mcqs", topic_data.get("questions", []))
                concepts = topic_data.get("concepts", [])
                
                # Filter history entries for this topic's concepts
                topic_history = [
                    entry for entry in interview_history
                    if entry.get("target_concept", "") in concepts
                    or entry.get("evaluation", {}).get("target_concept", "") in concepts
                ]
                
                # For the last topic, use the current knowledge_state
                # For previous topics, reconstruct from history
                if idx == state.get("current_topic_index", 0):
                    topic_ks = knowledge_state
                else:
                    # Reconstruct from history evaluations
                    topic_ks = _reconstruct_knowledge_state(topic_history, concepts)
                
                topics_data.append({
                    "topic": topic_name,
                    "knowledge_state": topic_ks,
                    "related_mcqs": related_mcqs,
                    "interview_history": topic_history,
                    "stop_reason": "",
                    "question_count": len(topic_history),
                })
        
        total_mcq_asked = sum(topic.get("no_of_questions", 0) for topic in all_topics)
        total_mcq_correct = sum(topic.get("no_of_crt_ans", 0) for topic in all_topics)
        
        data = {
            "thread_id": state.get("thread_id"),
            "topics": topics_data,
            "total_questions_asked": total_mcq_asked,
            "total_answered_correctly": total_mcq_correct,
            "total_topics": len(all_topics),
        }
        
        try:
            report_data = generate_report(data)
            return {"report": report_data}
        except Exception as e:
            print(f"Error generating report: {e}", file=sys.stderr)
            # Fallback that satisfies schema
            fallback_report = _build_fallback_report(
                topics_data, str(e),
                total_asked=total_mcq_asked,
                total_correct=total_mcq_correct,
            )
            return {"report": fallback_report}


def _reconstruct_knowledge_state(history: List[Dict], concepts: List[str]) -> Dict:
    """
    Reconstruct a topic's knowledge state from its interview history entries.
    Used for previous topics in multi-topic interviews where the live
    knowledge_state has already been replaced.
    """
    concept_beliefs = {}
    
    for concept in concepts:
        concept_beliefs[concept] = {
            "belief": "unknown",
            "confidence": 0.05,
            "evidence_count": 0,
            "evidence": [],
            "question_styles_used": [],
            "misconceptions": [],
            "last_updated_turn": 0,
            "information_gain": "",
        }
    
    for entry in history:
        eval_data = entry.get("evaluation", {})
        target = eval_data.get("target_concept", "")
        updated = eval_data.get("updated_concept", {})
        
        if target and target in concept_beliefs and updated:
            existing = concept_beliefs[target]
            # Merge evidence
            new_evidence = updated.get("evidence", [])
            existing["evidence"].extend(new_evidence)
            existing["evidence_count"] = len(existing["evidence"])
            # Update scalars
            existing["belief"] = updated.get("belief", existing["belief"])
            existing["confidence"] = updated.get("confidence", existing["confidence"])
            # Merge styles
            for style in updated.get("question_styles_used", []):
                if style not in existing["question_styles_used"]:
                    existing["question_styles_used"].append(style)
            # Merge misconceptions
            for misc in updated.get("misconceptions", []):
                if misc not in existing["misconceptions"]:
                    existing["misconceptions"].append(misc)
            existing["last_updated_turn"] = updated.get("last_updated_turn", existing["last_updated_turn"])
            existing["information_gain"] = updated.get("information_gain", "")
    
    return {"concepts": concept_beliefs}


def format_for_report(topics_data: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compress the raw topics_data (containing full knowledge_state, related_mcqs,
    and interview_history) into the lean context the ReportGeneratorAgent needs.

    Output schema per topic:
    {
      "topic_name": "Arrays",
      "status": "Interviewed" | "MCQ Only (No Interview)",
      "mcq_performance": "4/4 correct",
      "assessed_concepts": [
        {
          "concept": "...",
          "belief": "strong",
          "confidence": 0.75,
          "evidence": ["..."],
          "misconceptions": ["..."]   # only present when non-empty
        }
      ],
      "interview_transcript": [
        {"Q": "...", "A": "..."}
      ],
      # --- OR, for MCQ-only topics ---
      "untested_concepts": ["...", "..."]
    }
    """
    lean_topics = []

    for td in topics_data:
        topic_name = td.get("topic", "Unknown")
        knowledge_state = td.get("knowledge_state", {"concepts": {}})
        related_mcqs = td.get("related_mcqs", [])
        interview_history = td.get("interview_history", [])

        # ── MCQ performance: "X/Y correct" ────────────────────────────────────
        total_mcqs = len(related_mcqs)
        correct_mcqs = sum(1 for q in related_mcqs if q.get("is_correct", False))
        mcq_performance = f"{correct_mcqs}/{total_mcqs} correct" if total_mcqs else "No MCQs"

        # ── Determine interview status ─────────────────────────────────────────
        concepts_map = knowledge_state.get("concepts", {})
        interviewed = any(
            c.get("evidence_count", len(c.get("evidence", []))) > 0
            for c in concepts_map.values()
        )

        if interviewed:
            # ── Flatten assessed concepts ──────────────────────────────────────
            assessed_concepts = []
            for concept_name, c in concepts_map.items():
                belief = c.get("belief", "unknown")
                confidence = c.get("confidence", 0.0)
                # Extract only the observation strings from evidence entries
                evidence_strings = [
                    e.get("observation", "")
                    for e in c.get("evidence", [])
                    if e.get("observation", "")
                ]
                misconceptions = c.get("misconceptions", [])

                entry: Dict[str, Any] = {
                    "concept": concept_name,
                    "belief": belief,
                    "confidence": round(confidence, 2),
                    "evidence": evidence_strings,
                }
                if misconceptions:
                    entry["misconceptions"] = misconceptions

                assessed_concepts.append(entry)

            # ── Strip transcript to {Q, A, time_taken} ─────────────────────────────
            transcript = [
                {
                    "Q": entry.get("question", ""),
                    "A": entry.get("student_answer", ""),
                    "time_taken_seconds": entry.get("time_taken_seconds", 0),
                }
                for entry in interview_history
                if entry.get("question") and entry.get("student_answer")
            ]

            lean_topics.append({
                "topic_name": topic_name,
                "status": "Interviewed",
                "mcq_performance": mcq_performance,
                "mcq_questions_asked": total_mcqs,
                "mcq_questions_correct": correct_mcqs,
                "assessed_concepts": assessed_concepts,
                "interview_transcript": transcript,
            })
        else:
            # ── MCQ-only: just list untested concept names ─────────────────────
            untested = list(concepts_map.keys())
            lean_topics.append({
                "topic_name": topic_name,
                "status": "MCQ Only (No Interview)",
                "mcq_performance": mcq_performance,
                "mcq_questions_asked": total_mcqs,
                "mcq_questions_correct": correct_mcqs,
                "untested_concepts": untested,
            })

    return {"topics": lean_topics}


def _build_fallback_report(
    topics_data: List[Dict],
    error_msg: str,
    total_asked: int = 0,
    total_correct: int = 0,
) -> Dict:
    """Build a minimal valid report when generation fails."""
    topic_analysis = []
    for td in topics_data:
        topic_analysis.append({
            "topic": td.get("topic", "Unknown"),
            "understanding_level": "insufficient_evidence",
            "depth": "superficial",
            "mcq_interview_consistency": "insufficient_evidence",
            "feedback": f"Error occurred: {error_msg}",
            "strengths": [],
            "knowledge_gaps": [],
            "misconceptions": [],
            "concept_breakdown": [],
        })
    
    return {
        "session_metrics": {
            "total_questions_asked": total_asked,
            "total_answered_correctly": total_correct,
        },
        "assessment_summary": {
            "overall_understanding": "insufficient_evidence",
            "summary": f"Failed to generate report: {error_msg}",
            "communication_skills": {
                "articulation": "Unknown due to error.",
                "confidence": "Unknown due to error."
            }
        },
        "topic_analysis": topic_analysis,
        "reasoning_profile": {
            "reasoning_depth": "superficial",
            "summary": f"Error occurred: {error_msg}",
        },
        "key_strengths": [],
        "priority_improvement_areas": [],
        "final_summary": f"Error generating report: {error_msg}",
    }


# ──────────────────────────────────────────────────────────────────────────────
# Report Generation
# ──────────────────────────────────────────────────────────────────────────────

# Allowed Enum Values for Validation
ALLOWED_UNDERSTANDING = {"strong", "moderate", "weak", "insufficient_evidence"}
ALLOWED_DEPTH = {"superficial", "basic", "moderate", "deep", "expert"}
ALLOWED_CONSISTENCY = {
    "consistent",
    "correct_mcq_but_shallow_understanding",
    "wrong_mcq_but_demonstrated_understanding",
    "mixed_evidence",
    "insufficient_evidence",
}


def validate_input_data(data: Dict[str, Any]) -> List[str]:
    """
    Validates that the lean report context contains required elements
    and extracts list of topic names.
    Accepts both 'topic_name' (lean format) and 'topic' (legacy) keys.
    """
    if not isinstance(data, dict):
        raise ValueError("Input data must be a JSON object (dictionary).")

    if "topics" not in data:
        raise ValueError("Input JSON is missing the required 'topics' array.")

    if not isinstance(data["topics"], list):
        raise ValueError("Input 'topics' key must map to a list.")

    input_topics = []
    for idx, item in enumerate(data["topics"]):
        if not isinstance(item, dict):
            raise ValueError(f"Topic item at index {idx} must be a dictionary.")
        # Support both lean ('topic_name') and legacy ('topic') keys
        topic_name = item.get("topic_name") or item.get("topic", "")
        if not topic_name:
            raise ValueError(f"Topic name at index {idx} cannot be empty (needs 'topic_name' or 'topic' key).")
        input_topics.append(topic_name)

    return input_topics


def clean_llm_json_response(response: str) -> str:
    """
    Removes markdown code fences (e.g. ```json ... ``` or ``` ... ```)
    from the LLM string response.
    """
    text_cleaned = response.strip()

    # Check for fenced code block patterns
    match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text_cleaned)
    if match:
        return match.group(1).strip()
    return text_cleaned


def validate_report(report: Dict[str, Any], input_topics: List[str]) -> None:
    """
    Validates that the generated report conforms to the strict schema requirements
    and contains all assessed topics.
    """
    if not isinstance(report, dict):
        raise ValueError(f"Validation Error: Report must be a dictionary, got {type(report).__name__}")

    # 1. Required top-level keys
    required_keys = {
        "session_metrics",
        "assessment_summary",
        "topic_analysis",
        "reasoning_profile",
        "key_strengths",
        "priority_improvement_areas",
        "final_summary",
    }
    missing_keys = required_keys - set(report.keys())
    if missing_keys:
        raise ValueError(f"Validation Error: Missing required top-level keys: {missing_keys}")

    # 2. Check assessment_summary structure
    summary_section = report["assessment_summary"]
    if not isinstance(summary_section, dict):
        raise ValueError("Validation Error: 'assessment_summary' must be a dictionary.")
    if "overall_understanding" not in summary_section or "summary" not in summary_section:
        raise ValueError("Validation Error: 'assessment_summary' must contain 'overall_understanding' and 'summary'.")

    overall_und = summary_section["overall_understanding"]
    if overall_und not in ALLOWED_UNDERSTANDING:
        raise ValueError(f"Validation Error: Invalid overall_understanding '{overall_und}'. Allowed: {ALLOWED_UNDERSTANDING}")

    # 3. Check reasoning_profile structure
    reasoning_section = report["reasoning_profile"]
    if not isinstance(reasoning_section, dict):
        raise ValueError("Validation Error: 'reasoning_profile' must be a dictionary.")
    if "reasoning_depth" not in reasoning_section or "summary" not in reasoning_section:
        raise ValueError("Validation Error: 'reasoning_profile' must contain 'reasoning_depth' and 'summary'.")

    reasoning_depth = reasoning_section["reasoning_depth"]
    if reasoning_depth not in ALLOWED_DEPTH:
        raise ValueError(f"Validation Error: Invalid reasoning_depth '{reasoning_depth}'. Allowed: {ALLOWED_DEPTH}")

    # 4. Check array types
    if not isinstance(report["key_strengths"], list):
        raise ValueError("Validation Error: 'key_strengths' must be a list.")
    if not isinstance(report["priority_improvement_areas"], list):
        raise ValueError("Validation Error: 'priority_improvement_areas' must be a list.")
    if not isinstance(report["final_summary"], str):
        raise ValueError("Validation Error: 'final_summary' must be a string.")

    # 5. Check topic_analysis structure
    topic_analysis_list = report["topic_analysis"]
    if not isinstance(topic_analysis_list, list):
        raise ValueError("Validation Error: 'topic_analysis' must be a list.")

    generated_topics = []

    topic_required_fields = {
        "topic",
        "understanding_level",
        "depth",
        "mcq_interview_consistency",
        "feedback",
        "strengths",
        "knowledge_gaps",
        "misconceptions",
    }

    for idx, item in enumerate(topic_analysis_list):
        if not isinstance(item, dict):
            raise ValueError(f"Validation Error: Topic item at index {idx} in 'topic_analysis' must be a dictionary.")

        missing_fields = topic_required_fields - set(item.keys())
        if missing_fields:
            raise ValueError(f"Validation Error: Topic item at index {idx} is missing fields: {missing_fields}")

        topic_name = item["topic"]
        generated_topics.append(topic_name)

        # Validate lists inside topic analysis
        if not isinstance(item["strengths"], list):
            raise ValueError(f"Validation Error: 'strengths' for topic '{topic_name}' must be a list.")
        if not isinstance(item["knowledge_gaps"], list):
            raise ValueError(f"Validation Error: 'knowledge_gaps' for topic '{topic_name}' must be a list.")
        if not isinstance(item["misconceptions"], list):
            raise ValueError(f"Validation Error: 'misconceptions' for topic '{topic_name}' must be a list.")

        # Validate enums
        und_lvl = item["understanding_level"]
        if und_lvl not in ALLOWED_UNDERSTANDING:
            raise ValueError(f"Validation Error: Invalid understanding_level '{und_lvl}' in topic '{topic_name}'. Allowed: {ALLOWED_UNDERSTANDING}")

        depth = item["depth"]
        if depth not in ALLOWED_DEPTH:
            raise ValueError(f"Validation Error: Invalid depth '{depth}' in topic '{topic_name}'. Allowed: {ALLOWED_DEPTH}")

        consistency = item["mcq_interview_consistency"]
        if consistency not in ALLOWED_CONSISTENCY:
            raise ValueError(f"Validation Error: Invalid mcq_interview_consistency '{consistency}' in topic '{topic_name}'. Allowed: {ALLOWED_CONSISTENCY}")

    # 6. Verify one-to-one matching of topics (order-independent)
    input_set = set(input_topics)
    generated_set = set(generated_topics)

    if len(generated_topics) != len(generated_set):
        raise ValueError(f"Validation Error: Duplicate topics found in topic_analysis: {generated_topics}")

    missing_topics = input_set - generated_set
    if missing_topics:
        raise ValueError(f"Validation Error: The following assessed topics are missing from the report: {missing_topics}")

    extra_topics = generated_set - input_set
    if extra_topics:
        raise ValueError(f"Validation Error: The report contains unauthorized topics not in the input: {extra_topics}")


def generate_report(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generates the final assessment report from a pre-compressed lean context.

    format_for_report() is called first to reduce the full state into the
    minimal payload the LLM needs, eliminating raw MCQs, evaluator metadata,
    and untested-concept bloat.
    """
    # Compress full state into lean context before touching the LLM
    topics_data = data.get("topics", [])
    lean_data = format_for_report(topics_data)
    lean_data["thread_id"] = data.get("thread_id")

    # Inject session metrics into the context so the LLM can reference them
    total_asked = data.get("total_questions_asked", 0)
    total_correct = data.get("total_answered_correctly", 0)
    lean_data["session_metrics"] = {
        "total_questions_asked": total_asked,
        "total_answered_correctly": total_correct,
    }

    # Validate using the lean format
    input_topics = validate_input_data(lean_data)

    # Get LLM Client
    client = get_llm_client()

    system_prompt = (
        "You are ReportGeneratorAgent, the final synthesis agent in a scientific adaptive assessment system.\n"
        "Your job is to synthesize the compressed assessment data into a concise, evidence-based report.\n\n"

        "## Input Schema\n"
        "You receive a lean, pre-compressed context. Each topic has ONE of two shapes:\n\n"

        "INTERVIEWED topic:\n"
        "{\n"
        "  \"topic_name\": \"Arrays\",\n"
        "  \"status\": \"Interviewed\",\n"
        "  \"mcq_performance\": \"4/4 correct\",\n"
        "  \"assessed_concepts\": [\n"
        "    {\n"
        "      \"concept\": \"Zero-Based Indexing\",\n"
        "      \"belief\": \"misconception\",\n"
        "      \"confidence\": 0.25,\n"
        "      \"evidence\": [\"Observation string 1\", \"Observation string 2\"],\n"
        "      \"misconceptions\": [\"...\"]\n"
        "    }\n"
        "  ],\n"
        "  \"interview_transcript\": [{\"Q\": \"...\", \"A\": \"...\"}]\n"
        "}\n\n"

        "MCQ-ONLY topic (no interview was conducted):\n"
        "{\n"
        "  \"topic_name\": \"Queues\",\n"
        "  \"status\": \"MCQ Only (No Interview)\",\n"
        "  \"mcq_performance\": \"4/4 correct\",\n"
        "  \"untested_concepts\": [\"FIFO\", \"Enqueue\", \"Dequeue\"]\n"
        "}\n\n"

        "The input also includes session_metrics with total_questions_asked and total_answered_correctly.\n"
        "You MUST include these exact values in your output under the session_metrics key.\n\n"

        "## Rules\n"
        "- For INTERVIEWED topics: use 'assessed_concepts' (belief + confidence + evidence strings) as PRIMARY truth.\n"
        "  Use 'interview_transcript' ONLY to pull a supporting direct quote when useful.\n"
        "- For MCQ-ONLY topics: set understanding_level = 'insufficient_evidence' and note the untested concepts.\n"
        "- mcq_performance is an aggregated string (e.g. '4/4 correct'). Use it to assess MCQ vs interview consistency.\n"
        "- Do NOT reconstruct knowledge from the transcript. The assessed_concepts are the truth.\n"
        "- Do not invent misconceptions or mastered concepts.\n"
        "- Do not narrate every Q&A. Identify patterns across evidence strings.\n"
        "- Tone: concise, diagnostic, professional, student-friendly, evidence-based.\n\n"

        "## Consistency Classification\n"
        "For every topic, classify 'mcq_interview_consistency' as EXACTLY one of:\n"
        "- 'consistent': MCQ correct + assessed_concepts show strong/mastered beliefs\n"
        "- 'correct_mcq_but_shallow_understanding': MCQ correct but beliefs are partial/emerging\n"
        "- 'wrong_mcq_but_demonstrated_understanding': MCQ incorrect but beliefs are strong\n"
        "- 'mixed_evidence': Contradictory beliefs across concepts\n"
        "- 'insufficient_evidence': MCQ Only or not enough evidence\n\n"

        "## Formatting Constraints\n"
        "- understanding_level: 'strong' | 'moderate' | 'weak' | 'insufficient_evidence'\n"
        "- depth: 'superficial' | 'basic' | 'moderate' | 'deep' | 'expert'\n"
        "  (never use 'expert' unless evidence strongly demonstrates advanced reasoning)\n\n"

        "## Output Schema\n"
        "{\n"
        "  \"session_metrics\": {\n"
        "    \"total_questions_asked\": 12,\n"
        "    \"total_answered_correctly\": 8,\n"
        "    \"total_topics\": 3\n"
        "  },\n"
        "  \"assessment_summary\": {\n"
        "    \"overall_understanding\": \"strong | moderate | weak | insufficient_evidence\",\n"
        "    \"summary\": \"Concise overall interpretation.\",\n"
        "    \"communication_skills\": {\n"
        "      \"articulation\": \"Assess how clearly and structurally the student explained concepts (1-2 sentences).\",\n"
        "      \"confidence\": \"Assess the student's confidence based on their language and directness (1-2 sentences).\"\n"
        "    }\n"
        "  },\n"
        "  \"topic_analysis\": [\n"
        "    {\n"
        "      \"topic\": \"Exact topic_name from input\",\n"
        "      \"understanding_level\": \"strong | moderate | weak | insufficient_evidence\",\n"
        "      \"depth\": \"superficial | basic | moderate | deep | expert\",\n"
        "      \"mcq_interview_consistency\": \"...\",\n"
        "      \"mcq_questions_asked\": 4,\n"
        "      \"mcq_questions_correct\": 3,\n"
        "      \"average_time_taken_seconds\": 45,\n"
        "      \"feedback\": \"Synthesis of what the student understands.\",\n"
        "      \"strengths\": [\"Evidence-supported strength\"],\n"
        "      \"knowledge_gaps\": [\"Evidence-supported gap\"],\n"
        "      \"misconceptions\": [\"Evidence-supported misconception\"],\n"
        "      \"concept_breakdown\": [\n"
        "        {\n"
        "          \"concept\": \"Concept name\",\n"
        "          \"belief\": \"unknown | emerging | partial | strong | mastered | misconception\",\n"
        "          \"confidence\": 0.75,\n"
        "          \"key_evidence\": \"1-2 sentence synthesis of the evidence strings\"\n"
        "        }\n"
        "      ]\n"
        "    }\n"
        "  ],\n"
        "  \"reasoning_profile\": {\n"
        "    \"reasoning_depth\": \"superficial | basic | moderate | deep | expert\",\n"
        "    \"summary\": \"Cross-topic reasoning analysis.\"\n"
        "  },\n"
        "  \"key_strengths\": [\"Major strength\"],\n"
        "  \"priority_improvement_areas\": [\"Priority area\"],\n"
        "  \"final_summary\": \"Short descriptive final conclusion.\"\n"
        "}\n\n"

        "## Strict Output Rules\n"
        "- Return ONLY valid JSON. No markdown. No text outside the JSON object.\n"
        "- The 'topic' field in each topic_analysis entry MUST exactly match 'topic_name' from the input.\n"
        "- Include every topic exactly once.\n"
        "- Never fabricate assessment evidence.\n"
        "- The session_metrics values MUST match the input session_metrics exactly.\n"
    )

    user_prompt = (
        "Generate the final assessment report from this compressed assessment context.\n"
        "Use assessed_concepts as truth. Use interview_transcript only for direct quotes.\n\n"
        f"{json.dumps(lean_data, indent=2, ensure_ascii=False)}"
    )

    # Invoke LLM
    response_raw = client.generate_response(
        prompt=user_prompt,
        history=[],
        system_prompt=system_prompt,
        thread_id=data.get("thread_id"),
        agent_name="ReportGeneratorAgent",
        max_tokens=8192
    )

    # Clean & Parse JSON
    cleaned_response = clean_llm_json_response(response_raw)
    try:
        report = json.loads(cleaned_response)
    except json.JSONDecodeError as e:
        print("\n[DEBUG] Raw LLM Response that failed parsing:")
        print(response_raw)
        print("-" * 50)
        raise ValueError(f"Failed to parse LLM response as JSON: {e}")

    # Override session_metrics with deterministic values (don't trust LLM for numbers)
    report["session_metrics"] = {
        "total_questions_asked": total_asked,
        "total_answered_correctly": total_correct,
    }

    # Validate Constraints and Topic Coverage
    # The report uses 'topic' keys that must match the 'topic_name' values from the lean input
    validate_report(report, input_topics)

    return report

