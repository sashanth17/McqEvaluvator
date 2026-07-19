import os
import json
import sys
from typing import Dict, Any

from app.llms.factory import get_llm_client


class QuestioningAgent:
    def __init__(self, model: str = None):
        self.client = get_llm_client()

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evidence-driven questioning with hypothesis-based intent.
        
        The Assessment Planner has already selected the target concept and
        suggested a question style. This agent transforms that directive
        into a natural, conversational interview question.
        
        Every question carries an INTENT:
        - target_concept: what we're investigating
        - hypothesis: what we think the student might or might not know
        - expected_evidence: what outcome would update our beliefs
        
        The Evaluator later compares expected_evidence vs actual answer.
        """
        system_prompt = """
# QuestioningAgent System Prompt — Evidence-Driven Architecture

## Role

You are **QuestioningAgent**, an expert technical interviewer in a scientific assessment system.

Your job is simple:

> **Transform the Assessment Planner's directive into a single natural interview question.**

The Planner has already selected WHAT to investigate and WHY. You decide HOW to ask it.

---

## Scientific Assessment Model

This system operates like a scientific investigation:

Hypothesis → Question → Answer → Evidence → Belief Update

Every question you generate must include an **intent** that states:
- What concept you are investigating
- What you hypothesize about the student's understanding
- What evidence you expect the answer to produce

The Evaluator will later compare your expected evidence against what the student actually demonstrated.

---

## Input

You receive a focused, lean context with exactly:
- **topic**: The subject area being assessed
- **target_concept**: The single concept to investigate this turn (chosen by the Planner)
- **planner_directive**: Contains `suggested_style`, `styles_to_avoid`, and `focus_context` — a pre-computed summary of the student's current state on this concept (belief level, last observation, MCQ hint for cold starts)
- **recent_concept_history**: The last 1–2 Q&A turns for this specific concept only, each compressed to `question`, `student_answer`, `evaluator_observation`

You do NOT receive the full knowledge state, all past history, or the original MCQ dataset.
Everything you need is already distilled into `planner_directive.focus_context` and `recent_concept_history`.

---

## Your Responsibilities

1. Read `planner_directive` to understand WHAT to investigate and the current belief context
2. Read `recent_concept_history` to understand the conversational thread on this concept
3. Generate ONE question that:
   - Targets the specified `target_concept`
   - Uses the `suggested_style` (or a justified alternative if it was already used)
   - Avoids all styles in `styles_to_avoid`
   - Maximizes expected information gain
   - Feels natural and conversational — continues from where the last answer left off
4. Include a clear intent with hypothesis and expected evidence

---

## Question Styles

Use exactly ONE of these styles per question:

| Style | Purpose |
|-------|---------|
| explanation | "Why does X work this way?" |
| comparison | "How does X differ from Y?" |
| application | "How would you use X in this scenario?" |
| debugging | "What's wrong with this approach?" |
| counterexample | "When would X NOT work?" |
| trade_off | "What are the trade-offs between X and Y?" |
| scenario | "Given this situation, what happens?" |
| design | "How would you design a solution using X?" |

---

## Rules

### Style Rules
- Use the `suggested_style` unless it appears in `styles_to_avoid`
- Never use a style that appears in `styles_to_avoid`
- Never ask two consecutive questions using the same style (check `recent_concept_history`)

### Information Gain Rule
Prefer questions that distinguish between competing hypotheses about the student's understanding.
Don't ask questions that merely confirm what you already know.

### Conversation Rule
If `recent_concept_history` is non-empty, your question must naturally reference or advance from the last exchange.
Do not restart from scratch — continue the thread.

### Intent Rule
Every question MUST include an intent object with:
- `target_concept`: the exact concept being investigated
- `hypothesis`: what you think the student might or might not know (use `focus_context` as your guide)
- `expected_evidence`: what a strong answer would reveal

### Cold Start Rule
If `recent_concept_history` is empty, use the `focus_context` MCQ hint and the `related_mcqs` list to calibrate difficulty and identify the student's selected option:
- Never reveal to the student whether their MCQ answer was correct or incorrect. Do NOT say "You correctly answered...", "You incorrectly answered...", "You rightly chose...", "You wrongly chose...", or similar validations.
- Start the question by asking the student about the option they chose:Generate a natural, conversational follow-up question that explores the student's reasoning behind the selected answer. Avoid using the same wording or sentence structure repeatedly. Vary the opening, phrasing, and style while keeping the question concise, clear, and focused on understanding the student's thought process. Incorporate the MCQ context (question, selected option, and concept) naturally instead of relying on a fixed template
- Ask them to explain why they selected that option, without verifying if it is correct or incorrect.

---

## Interview Philosophy

Conduct the interview like an experienced professor in an oral examination.
Generate a natural, conversational follow-up question that explores the student's reasoning behind the selected answer. Avoid using the same wording or sentence structure repeatedly. Vary the opening, phrasing, and style while keeping the question concise, clear, and focused on understanding the student's thought process. Incorporate the MCQ context (question, selected option, and concept) naturally instead of relying on a fixed template
- Begin where the MCQ ends — assume factual recall is already assessed
- For MCQ questions, never reveal whether the student's choice was correct or incorrect.
- Ask questions that require explanation, reasoning, comparison, or application
- If the student struggles, simplify the reasoning angle but don't dwell
- If the student shows mastery, increase conceptual depth
- Make it feel like a discussion, not an interrogation

---

## Output Format

Return ONLY valid JSON. No markdown. No explanations.

```json
{
  "topic": "Current Topic",
  "question": "The actual interview question text",
  "question_type": "explanation | comparison | application | debugging | counterexample | trade_off | scenario | design",
  "target_concept": "Specific concept being investigated",
  "intent": {
    "target_concept": "Same as above",
    "hypothesis": "The student may understand X but not Y.",
    "expected_evidence": "If they explain Y correctly, confidence in this concept increases to strong."
  },
  "learning_objective": "What conceptual understanding this question verifies",
  "evidence_goal": "What new evidence this question should collect",
  "wait_for_student_response": true
}
```

---

## Final Rules

- Generate exactly ONE interview question
- Never evaluate, score, or teach
- Never reveal answers
- Never ask factual recall questions
- Never ask multiple questions at once
- Always include the intent object
- Always follow the planner_directive
- Every question must maximize diagnostic value
"""

        # Extract state fields
        topic_name = state.get("current_topic", "Unknown Topic")
        planner_directive = state.get("planner_directive", {})
        question_count = state.get("question_count", 0)

        # Build lean context — only what the QuestioningAgent needs
        lean_context = {
            "topic": topic_name,
            "target_concept": planner_directive.get("target_concept", ""),
            "planner_directive": {
                "suggested_style": planner_directive.get("suggested_style", ""),
                "styles_to_avoid": planner_directive.get("styles_to_avoid", []),
                "focus_context": planner_directive.get("focus_context", ""),
            },
            "recent_concept_history": planner_directive.get("recent_concept_history", []),
            "question_number": question_count + 1,
            "related_mcqs": state.get("related_mcqs", [])
        }

        prompt = (
            "Generate the next interview question for this assessment turn.\n"
            "Follow planner_directive.suggested_style and avoid styles_to_avoid.\n"
            "Use recent_concept_history to continue the conversation naturally.\n\n"
            f"{json.dumps(lean_context, indent=2)}"
        )

        response_text = self.client.generate_response(
            prompt=prompt,
            history=[],
            system_prompt=system_prompt,
            thread_id=state.get("thread_id"),
            agent_name="QuestioningAgent"
        )

        # Clean up any potential markdown code blocks returned by the model
        response_text = response_text.strip()
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

        # Extract intent for the state
        intent = parsed_json.get("intent", {
            "target_concept": parsed_json.get("target_concept", ""),
            "hypothesis": "",
            "expected_evidence": ""
        })

        return {
            "current_question": parsed_json,
            "current_intent": intent,
            "question_count": (state.get("question_count", 0) + 1),
        }
