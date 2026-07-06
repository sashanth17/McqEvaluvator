import os
import json
import sys
from typing import Dict, Any

from app.llms.openRouter import OpenRouterClient

class ReportGeneratorAgent:
    def __init__(self, model: str = "google/gemini-2.5-flash"):
        api_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("API Key not found. Please set OPENROUTER_API_KEY environment variable.")
        self.client = OpenRouterClient(api_key=api_key, model=model)

    def run(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Reads the interview history and generates a descriptive final report.
        """
        topic_name = state.get("topic", "Unknown Topic")
        interview_history = state.get("interview_history", [])
        
        data = {
            "thread_id": state.get("thread_id"),
            "topics": [
                {
                    "topic": topic_name,
                    "interview_history": interview_history,
                    "related_questions": state.get("related_questions", [])
                }
            ]
        }
        
        try:
            report_data = generate_report(data)
            return {"report": report_data}
        except Exception as e:
            print(f"Error generating report: {e}", file=sys.stderr)
            # fallback that satisfies schema
            fallback_report = {
                "assessment_summary": {
                    "overall_understanding": "insufficient_evidence",
                    "summary": f"Failed to generate report: {str(e)}"
                },
                "topic_analysis": [
                    {
                        "topic": topic_name,
                        "understanding_level": "insufficient_evidence",
                        "depth": "superficial",
                        "mcq_interview_consistency": "insufficient_evidence",
                        "feedback": "Error occurred.",
                        "strengths": [],
                        "knowledge_gaps": [],
                        "misconceptions": []
                    }
                ],
                "reasoning_profile": {
                    "reasoning_depth": "superficial",
                    "summary": "Error occurred."
                },
                "key_strengths": [],
                "priority_improvement_areas": [],
                "final_summary": "Error generating report."
            }
            return {"report": fallback_report}


#!/usr/bin/env python3
"""
Standalone Final Assessment Report Generator
Reads assessment evidence JSON, calls OpenRouter to synthesize the report,
validates the response format and content constraints, and saves the final JSON.
"""

import os
import sys
import json
import time
import re
from typing import List, Dict, Any

# Try importing dotenv, or parse manually to keep the script standalone
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    if os.path.exists(".env"):
        with open(".env", "r", encoding="utf-8") as f:
            for line in f:
                if line.strip().startswith("OPENROUTER_API_KEY="):
                    val = line.split("=", 1)[1].strip()
                    if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                        val = val[1:-1]
                    os.environ["OPENROUTER_API_KEY"] = val

# Configuration variables (easily configurable)
INPUT_JSON = "assessment_input.json"
OUTPUT_JSON = "assessment_report.json"

# Allowed Enum Values for Validation
ALLOWED_UNDERSTANDING = {"strong", "moderate", "weak", "insufficient_evidence"}
ALLOWED_DEPTH = {"superficial", "basic", "moderate", "deep", "expert"}
ALLOWED_CONSISTENCY = {
    "consistent",
    "correct_mcq_but_shallow_understanding",
    "wrong_mcq_but_demonstrated_understanding",
    "mixed_evidence",
    "insufficient_evidence"
}

def load_json(file_path: str) -> Dict[str, Any]:
    """Loads a JSON file and returns the parsed dictionary."""
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Input file not found at: {file_path}")
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        raise ValueError(f"Failed to parse input JSON from {file_path}: {e}")

def validate_input_data(data: Dict[str, Any]) -> List[str]:
    """
    Validates that the input assessment context contains required elements
    and extracts list of assessed topics.
    """
    if not isinstance(data, dict):
        raise ValueError("Input data must be a JSON object (dictionary).")
    
    if "topics" not in data:
        raise ValueError("Input JSON is missing the required 'topics' array.")
    
    if not isinstance(data["topics"], list):
        raise ValueError("Input 'topics' key must map to a list.")
        
    input_topics = []
    for idx, item in enumerate(data["topics"]):
        if not isinstance(item, dict) or "topic" not in item:
            raise ValueError(f"Topic item at index {idx} must be a dictionary containing 'topic' key.")
        topic_name = item["topic"]
        if not topic_name:
            raise ValueError(f"Topic name at index {idx} cannot be empty.")
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
        "assessment_summary",
        "topic_analysis",
        "reasoning_profile",
        "key_strengths",
        "priority_improvement_areas",
        "final_summary"
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
        
    # Compile generated topics
    generated_topics = []
    
    topic_required_fields = {
        "topic",
        "understanding_level",
        "depth",
        "mcq_interview_consistency",
        "feedback",
        "strengths",
        "knowledge_gaps",
        "misconceptions"
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

def save_json(data: Dict[str, Any], file_path: str) -> None:
    """Saves dictionary data to a JSON file format."""
    try:
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        raise IOError(f"Failed to write output JSON to {file_path}: {e}")

def generate_report(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sends the assessment context to OpenRouter and receives a non-streaming
    synthesized report. Performs cleaning, parsing, and validation.
    """
    # 1. Fetch API Key and instantiate client
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise ValueError("Missing required environment variable 'OPENROUTER_API_KEY'.")

    # Validate input format and extract expected topics
    input_topics = validate_input_data(data)
    
    # 2. Get OpenRouter Client
    model = os.getenv("OPENROUTER_MODEL") or "google/gemini-2.5-flash"
    client = OpenRouterClient(api_key=api_key, model=model)
    
    # 3. Formulate System Prompt and User Prompt
    system_prompt = (
        "You are ReportGeneratorAgent, the final synthesis agent in an adaptive technical assessment system.\n"
        "Your responsibility is to generate a concise, evidence-based assessment report describing the student's actual conceptual understanding across all assessed topics.\n"
        "You receive structured evidence collected from MCQ performance, related MCQ questions, adaptive interviews, student answers, and evaluator assessments.\n\n"
        
        "Follow these design guidelines when synthesizing this evidence:\n"
        "- Do not simply repeat scores.\n"
        "- Do not narrate every question and answer.\n"
        "- Do not produce a chronological interview transcript.\n"
        "- Identify patterns in the student's understanding.\n"
        "- Ground every major conclusion in the supplied assessment evidence. Prefer evaluator evidence and evidence ledgers when determining conceptual understanding. Use student answers only to provide context or resolve ambiguity.\n"
        "- Do not invent misconceptions or mastered concepts.\n"
        "- Do not infer confidence from writing style.\n"
        "- Tone must be concise, descriptive, diagnostic, professional, student-friendly, and evidence-based.\n"
        "- Explain: what the student genuinely understands, how deeply, where reasoning becomes weak, important misconceptions, missing concepts, whether MCQ performance matches interview evidence, major strengths, and priority improvement areas.\n\n"
        
        "Consistency Classification Rules:\n"
        "For every topic, compare MCQ performance with interview evidence and classify 'mcq_interview_consistency' into EXACTLY one of the following:\n"
        "- 'consistent': The student answered the MCQ correctly and demonstrated strong conceptual reasoning.\n"
        "- 'correct_mcq_but_shallow_understanding': The student answered correctly but follow-up questioning exposed weak understanding.\n"
        "- 'wrong_mcq_but_demonstrated_understanding': The student answered incorrectly but demonstrated sound conceptual knowledge during the interview.\n"
        "- 'mixed_evidence': The evidence is contradictory or inconclusive.\n"
        "- 'insufficient_evidence': There is not enough evidence to draw a conclusion.\n"
        "* Do not claim the student guessed unless the supplied evidence explicitly supports that conclusion.\n\n"
        
        "Formatting Constraints:\n"
        "- Use only these understanding levels: 'strong', 'moderate', 'weak', 'insufficient_evidence'.\n"
        "- Use only these depth levels: 'superficial', 'basic', 'moderate', 'deep', 'expert'. Do not use 'expert' unless the supplied evidence strongly demonstrates advanced reasoning, transfer, edge-case handling, or generalization.\n\n"
        
        "Strict Formatting Output Rules:\n"
        "- Return ONLY valid JSON.\n"
        "- Include every assessed topic exactly once.\n"
        "- Preserve topic names from the input exactly.\n"
        "- Never add topics that do not exist in the input.\n"
        "- Never omit assessed topics.\n"
        "- Never return markdown code blocks (e.g. do not wrap in ```json or ```).\n"
        "- Never return any plain text outside of the JSON object.\n"
        "- Never ask follow-up questions.\n"
        "- Never expose internal LLM reasoning.\n"
        "- Never mention agents or implementation architecture.\n"
        "- Never fabricate assessment evidence.\n"
        "- Never generate percentages that are not present in the input.\n"
        "- Never predict future test scores.\n"
        "- Never diagnose intelligence, personality, learning disabilities, or other unsupported student traits.\n\n"
        
        "Your output MUST exactly follow this JSON schema:\n"
        "{\n"
        "  \"assessment_summary\": {\n"
        "    \"overall_understanding\": \"strong | moderate | weak | insufficient_evidence\",\n"
        "    \"summary\": \"Concise overall interpretation of the student's performance and demonstrated understanding.\"\n"
        "  },\n"
        "  \"topic_analysis\": [\n"
        "    {\n"
        "      \"topic\": \"Topic name\",\n"
        "      \"understanding_level\": \"strong | moderate | weak | insufficient_evidence\",\n"
        "      \"depth\": \"superficial | basic | moderate | deep | expert\",\n"
        "      \"mcq_interview_consistency\": \"consistent | correct_mcq_but_shallow_understanding | wrong_mcq_but_demonstrated_understanding | mixed_evidence | insufficient_evidence\",\n"
        "      \"feedback\": \"Descriptive synthesis of what the student understands, where reasoning becomes weak, and what the evidence indicates.\",\n"
        "      \"strengths\": [\n"
        "        \"Evidence-supported strength\"\n"
        "      ],\n"
        "      \"knowledge_gaps\": [\n"
        "        \"Evidence-supported knowledge gap\"\n"
        "      ],\n"
        "      \"misconceptions\": [\n"
        "        \"Evidence-supported misconception\"\n"
        "      ]\n"
        "    }\n"
        "  ],\n"
        "  \"reasoning_profile\": {\n"
        "    \"reasoning_depth\": \"superficial | basic | moderate | deep | expert\",\n"
        "    \"summary\": \"Cross-topic analysis of the student's reasoning style and conceptual depth.\"\n"
        "  },\n"
        "  \"key_strengths\": [\n"
        "    \"Major cross-topic strength\"\n"
        "  ],\n"
        "  \"priority_improvement_areas\": [\n"
        "    \"Highest-priority improvement area\"\n"
        "  ],\n"
        "  \"final_summary\": \"Short descriptive final conclusion about the student's actual understanding and performance on the test.\"\n"
        "}"
    )

    user_prompt = (
        "Generate the final assessment report for the following input assessment evidence:\n\n"
        f"{json.dumps(data, indent=2, ensure_ascii=False)}"
    )

    # 4. Invoke LLM (Non-Streaming)
    response_raw = client.generate_response(
        prompt=user_prompt,
        history=[],
        system_prompt=system_prompt,
        thread_id=data.get("thread_id"),
        agent_name="ReportGeneratorAgent"
    )
    
    # 5. Clean & Parse JSON
    cleaned_response = clean_llm_json_response(response_raw)
    try:
        report = json.loads(cleaned_response)
    except json.JSONDecodeError as e:
        print("\n[DEBUG] Raw LLM Response that failed parsing:")
        print(response_raw)
        print("-" * 50)
        raise ValueError(f"Failed to parse LLM response as JSON: {e}")

    # 6. Validate Constraints and Topic Coverage
    validate_report(report, input_topics)
    
    return report

if __name__ == "__main__":
    start_time = time.time()
    
    print(f"Loading input file: {INPUT_JSON}...")
    try:
        input_data = load_json(INPUT_JSON)
    except Exception as e:
        print(f"Error loading input JSON: {e}", file=sys.stderr)
        sys.exit(1)

    print("Generating assessment report using OpenRouter...")
    try:
        report_data = generate_report(input_data)
    except Exception as e:
        print(f"Error during report generation: {e}", file=sys.stderr)
        sys.exit(1)

    print(f"Saving report to: {OUTPUT_JSON}...")
    try:
        save_json(report_data, OUTPUT_JSON)
    except Exception as e:
        print(f"Error saving output JSON: {e}", file=sys.stderr)
        sys.exit(1)

    elapsed = time.time() - start_time
    print(f"Success! Generated assessment report saved to {OUTPUT_JSON} (took {elapsed:.2f}s)")
