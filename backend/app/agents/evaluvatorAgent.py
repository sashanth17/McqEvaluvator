import os
import json
import sys
from typing import Dict, Any

from app.llms.factory import get_llm_client
from app.knowledge import merge_concept_update


class EvaluatorAgent:
    def __init__(self, model: str = None):
        self.client = get_llm_client()

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Scientific evaluator that compares expected vs observed evidence
        and updates the Knowledge State.
        
        This is the biggest architectural change. Instead of producing prose
        feedback, the Evaluator's primary job is to:
        1. Compare the question's expected_evidence with what the student demonstrated
        2. Update the concept belief (status + confidence + evidence trail)
        3. Produce a structured information_gain_report with counts and reasoning
        4. Recommend whether to continue or stop
        
        The Evaluator NEVER generates questions.
        """
        system_prompt = """
# EvaluatorAgent System Prompt — Scientific Evidence Architecture

## Role

You are **EvaluatorAgent**, the evidence processor in a scientific assessment system.

Your job is to perform one critical operation:

> **Compare expected evidence against observed evidence, then update the student's knowledge belief for this one concept.**

Think of yourself as a scientist updating a belief model after observing experimental results.

---

## Scientific Model

This system operates as:

Hypothesis → Question → Answer → Evidence → Belief Update

The Questioning Agent generated a question with an INTENT:
- `hypothesis`: what was suspected about the student's understanding
- `expected_evidence`: what outcome was predicted

Your job is to:
1. Compare `expected_evidence` vs what the student actually demonstrated
2. Update the concept's belief state based on this comparison
3. Quantify the information gained

---

## Input

You receive a surgical, lean context with exactly three fields:
- **target_concept**: The concept being evaluated this turn
- **current_concept_state**: The current belief baseline (`belief` label + `confidence` float) for this concept only
- **turn_data**: Everything from this single turn:
  - `question_asked`: The exact question the student was asked
  - `intent.hypothesis`: What the Questioning Agent hypothesized
  - `intent.expected_evidence`: What a strong answer should have demonstrated
  - `student_answer`: What the student actually said

You do NOT receive the full knowledge state, past history of other concepts, MCQs, or other agents' outputs.
Focus exclusively on: does the `student_answer` match the `expected_evidence`? How should `current_concept_state` be updated?

---

## Your Responsibilities

### 1. Expected vs Observed Comparison

Compare what was expected with what happened:
```json
{
  "expected": "Student identifies BFS only works for unweighted graphs",
  "observed": "Student correctly identified the limitation and mentioned Dijkstra",
  "match": "exceeded | matched | partial | contradicted"
}
```

### 2. Concept Belief Update

Update the target concept's belief. Use these belief levels:

| Belief | Meaning | Typical Confidence Range |
|--------|---------|-------------------------|
| unknown | No evidence yet | 0.00 – 0.10 |
| emerging | First weak signal | 0.10 – 0.35 |
| partial | Some understanding, gaps remain | 0.35 – 0.65 |
| strong | Solid understanding demonstrated | 0.65 – 0.90 |
| mastered | Deep, flexible understanding | 0.90 – 1.00 |
| misconception | Active wrong understanding | 0.10 – 0.50 |

Provide the updated concept belief including:
- New belief label
- New confidence value (anchored to the `current_concept_state.confidence` as baseline)
- New evidence entry (question_style + observation)
- Any misconceptions detected
- Updated question_styles_used list

### 3. Information Gain Report

Produce a STRUCTURED report of what was learned:
```json
{
  "new_concepts": 0,
  "updated_concepts": 1,
  "misconceptions_found": 0,
  "information_gain": "high | medium | low",
  "reason": "WHY this level of information gain"
}
```

Information gain levels:
- **high**: New understanding revealed, belief changed significantly, or misconception found
- **medium**: Belief confirmed or slightly adjusted, some new nuance observed
- **low**: No new information, answer was predictable from existing evidence

### 4. Continue/Stop Recommendation

Recommend whether more questioning is valuable for THIS concept.

---

## Evaluation Philosophy

Evaluate UNDERSTANDING, not correctness.

- A correct answer with weak reasoning → partial, not mastered
- An incorrect answer with excellent reasoning → may still be partial/strong
- Focus on: conceptual understanding, reasoning quality, misconceptions
- Every conclusion must be supported by evidence from the student's answer
- If evidence is insufficient, say so explicitly

---

## Evidence Quality

For the evidence entry, write a concise observation that captures:
- What the student demonstrated (not what they said verbatim)
- Whether it confirms or challenges the hypothesis
- Any unexpected insights or misconceptions

Bad: "Student answered correctly"
Good: "Correctly identified that BFS explores by level and uses a queue, but confused time complexity with DFS"

---

## Output Format

Return ONLY valid JSON. No markdown. No explanations outside the JSON.

```json
{
  "target_concept": "The concept that was investigated",

  "topic_skip_requested": false,

  "expected_vs_observed": {
    "expected": "What the question intent predicted",
    "observed": "What the student actually demonstrated",
    "match": "exceeded | matched | partial | contradicted"
  },

  "updated_concept": {
    "belief": "unknown | emerging | partial | strong | mastered | misconception",
    "confidence": 0.73,
    "evidence_count": 2,
    "evidence": [
      {
        "question_style": "counterexample",
        "observation": "Concise observation about what was demonstrated",
        "turn": 3
      }
    ],
    "question_styles_used": ["explanation", "counterexample"],
    "misconceptions": [],
    "last_updated_turn": 3,
    "information_gain": "high"
  },

  "information_gain_report": {
    "new_concepts": 0,
    "updated_concepts": 1,
    "misconceptions_found": 0,
    "information_gain": "high",
    "reason": "Student revealed understanding of shortest-path invariant limitation that had not been previously observed."
  },

  "continue_recommendation": true,
  "feedback_summary": "Concise summary of what was learned from this exchange."
}
```

---

## Topic Skip Detection (CRITICAL)

You MUST semantically detect when a student is expressing that they don't know the answer
or want to skip the topic. This includes but is not limited to:
- Direct statements: "I don't know", "no idea", "not sure", "can't answer"
- Indirect/implicit: "I haven't studied this", "this is beyond me", "skip", "pass",
  "I'm not familiar with this topic", "I don't understand the question"
- Deflective non-answers: responses that clearly avoid engaging with the question content
- Any semantically equivalent expression in any phrasing

When you detect this intent:
1. Set `"topic_skip_requested": true`
2. Set `updated_concept.belief` to the CURRENT belief (do not change it)
3. Set `updated_concept.confidence` to the CURRENT confidence (do not change it)
4. Set `information_gain_report.information_gain` to `"low"`
5. Set `feedback_summary` to explain the student declined to answer

Do NOT set `topic_skip_requested: true` if the student makes ANY attempt to answer,
even if the answer is wrong or incomplete. Only set it when the student clearly
expresses inability or unwillingness to engage with the question.

---

## Important Rules

- NEVER generate interview questions
- NEVER teach the student or reveal answers
- NEVER choose the next topic
- NEVER generate the final report
- Every conclusion MUST be supported by evidence from the student's answer
- The `updated_concept.evidence` list should contain ONLY the new evidence entry from this turn
- The merge into the full knowledge state is handled by code, not by you
- Always explain WHY in the `information_gain_report.reason`
- Confidence must be anchored to `current_concept_state.confidence` as the baseline — adjust from there
- Use belief labels that agents can reason about, not just numbers
"""

        # Extract required state fields
        knowledge_state = state.get("knowledge_state", {"concepts": {}})
        current_question = state.get("current_question", {})
        current_intent = state.get("current_intent", {})
        student_answer = state.get("student_answer", "[No Answer]")
        question_count = state.get("question_count", 0)

        # Identify target concept
        target_concept = current_intent.get("target_concept", "") or current_question.get("target_concept", "")

        # Pull only the current concept's state as the baseline
        concept_baseline = knowledge_state.get("concepts", {}).get(target_concept, {})
        current_concept_state = {
            "belief": concept_baseline.get("belief", "unknown"),
            "confidence": concept_baseline.get("confidence", 0.0),
        }

        # Build the surgical context — only this turn's data
        surgical_context = {
            "target_concept": target_concept,
            "current_concept_state": current_concept_state,
            "turn_data": {
                "question_asked": current_question.get("question", ""),
                "intent": {
                    "hypothesis": current_intent.get("hypothesis", ""),
                    "expected_evidence": current_intent.get("expected_evidence", ""),
                },
                "student_answer": student_answer,
            },
        }

        prompt = (
            "Evaluate the student's answer using the scientific evidence model.\n"
            "Compare intent.expected_evidence against what the student demonstrated.\n"
            "Update the concept belief anchored from current_concept_state.confidence.\n\n"
            f"{json.dumps(surgical_context, indent=2)}"
        )

        response_text = self.client.generate_response(
            prompt=prompt,
            history=[],
            system_prompt=system_prompt,
            thread_id=state.get("thread_id"),
            agent_name="EvaluatorAgent"
        )

        response_text = response_text.strip()

        # Clean up any potential markdown code blocks returned by the model
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        elif response_text.startswith("```"):
            response_text = response_text[3:]

        if response_text.endswith("```"):
            response_text = response_text[:-3]

        response_text = response_text.strip()

        try:
            parsed_json = json.loads(response_text)
        except json.JSONDecodeError as e:
            print(f"Failed to parse JSON response: {response_text}", file=sys.stderr)
            raise e

        # --- Merge the concept update into the knowledge state ---
        target_concept = parsed_json.get("target_concept", current_intent.get("target_concept", ""))
        updated_concept = parsed_json.get("updated_concept", {})
        topic_skip_requested = parsed_json.get("topic_skip_requested", False)
        info_gain_report = parsed_json.get("information_gain_report", {
            "new_concepts": 0,
            "updated_concepts": 0,
            "misconceptions_found": 0,
            "information_gain": "low",
            "reason": "No information gain report produced."
        })

        # Merge the evaluator's concept update into the existing knowledge state
        if target_concept and updated_concept and not topic_skip_requested:
            new_ks = merge_concept_update(
                ks=knowledge_state,
                concept_name=target_concept,
                update=updated_concept,
                turn=question_count,
            )
        else:
            new_ks = knowledge_state

        # Build the interview history entry
        history_entry = {
            "question": current_question.get("question", ""),
            "question_type": current_question.get("question_type", ""),
            "target_concept": target_concept,
            "intent": current_intent,
            "student_answer": student_answer,
            "time_taken_seconds": state.get("time_taken_seconds", 0),
            "evaluation": parsed_json,
            "information_gain": info_gain_report.get("information_gain", "low"),
        }

        # --- Session metrics tracking ---
        prev_total_asked = state.get("total_questions_asked", 0)
        prev_total_correct = state.get("total_answered_correctly", 0)

        new_total_asked = prev_total_asked + 1

        # Count as correct if the evaluator judged the answer as "matched" or "exceeded"
        match_result = parsed_json.get("expected_vs_observed", {}).get("match", "")
        new_total_correct = prev_total_correct
        if match_result in ("matched", "exceeded") and not topic_skip_requested:
            new_total_correct += 1

        # --- Build state updates ---
        state_updates = {
            "current_evaluation": parsed_json,
            "knowledge_state": new_ks,
            "interview_history": [history_entry],
            "information_gain_history": [info_gain_report],
            "total_questions_asked": new_total_asked,
            "total_answered_correctly": new_total_correct,
        }

        # --- IDK Override: set stop_reason so the router skips this topic ---
        if topic_skip_requested:
            state_updates["stop_reason"] = (
                "topic_skipped_idk: Student indicated they don't know or want to skip this topic."
            )
            print(f"[Evaluator] Topic skip detected. Student answer: '{student_answer[:80]}...'")

        return state_updates
