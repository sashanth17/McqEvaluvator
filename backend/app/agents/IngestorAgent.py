#!/usr/bin/env python3
"""
Ingestor Agent — Single LLM Call Architecture

Reads a CSV of MCQ responses, classifies each question into a topic AND extracts
the key concepts being tested, all in a single LLM call per batch. Groups questions
by topic and produces structured output with concept maps.

This is the entry point of the evidence-driven assessment pipeline.
"""

import os
import sys
import json
import time
import concurrent.futures
import re
from typing import List, Dict, Any
from collections import defaultdict, Counter
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

from app.llms.factory import get_llm_client


def clean_str(val) -> str:
    """
    Converts pandas value to clean stripped string.
    Handles NaN values by returning an empty string.
    """
    if pd.isna(val):
        return ""
    return str(val).strip()


def parse_json_response(text: str, model_name: str = "Unknown", batch_no: int = 1) -> dict:
    """
    Cleans markdown code blocks (e.g. ```json ... ```) from LLM output
    and parses it into a dictionary. If parsing fails and output is plain text,
    uses a fallback mapping to wrap the output.
    """
    text_cleaned = text.strip()

    # Try finding markdown code block containing JSON
    match = re.search(r'```(?:json)?\s*([\s\S]*?)\s*```', text_cleaned)
    if match:
        json_str = match.group(1).strip()
    else:
        json_str = text_cleaned

    try:
        return json.loads(json_str)
    except json.JSONDecodeError as e:
        # Fallback handling: Check if it's plain text (not starting with typical JSON markers)
        if not (json_str.startswith("{") or json_str.startswith("[")):
            print(f"[Fallback] Model returned plain string instead of JSON. Converting automatically.", file=sys.stderr)
            return {
                "topics": [
                    {
                        "question_index": 0,
                        "topic": json_str,
                        "concepts": []
                    }
                ]
            }
        else:
            print(f"JSON parsing failed on malformed JSON: {e}", file=sys.stderr)
            raise ValueError(f"Failed to decode response as JSON (malformed JSON structure): {e}. Raw response: {text}")


def validate_llm_response(data: Any, require_topic: bool = True) -> None:
    """
    Validates that the response dict conforms to the expected schema
    with question_index, topic, and concepts.
    """
    if not isinstance(data, dict):
        raise ValueError(f"Validation Error: Expected dictionary response, got {type(data).__name__}")
    if "topics" not in data:
        raise ValueError("Validation Error: Missing 'topics' key in LLM response.")
    if not isinstance(data["topics"], list):
        raise ValueError(f"Validation Error: 'topics' must be a list, got {type(data['topics']).__name__}")

    for idx, item in enumerate(data["topics"]):
        if not isinstance(item, dict):
            raise ValueError(f"Validation Error: Topic item at index {idx} must be a dictionary, got {type(item).__name__}")
        if "question_index" not in item:
            raise ValueError(f"Validation Error: Topic item at index {idx} is missing the 'question_index' key.")
        if require_topic and "topic" not in item:
            raise ValueError(f"Validation Error: Topic item at index {idx} is missing the 'topic' key.")

        # Verify that question_index is/can be an integer
        try:
            int(item["question_index"])
        except (ValueError, TypeError):
            raise ValueError(f"Validation Error: 'question_index' at index {idx} must be an integer, got {item['question_index']}")

        # Concepts validation (optional but expected)
        if "concepts" in item:
            if not isinstance(item["concepts"], list):
                raise ValueError(f"Validation Error: 'concepts' at index {idx} must be a list, got {type(item['concepts']).__name__}")


def classify_topics_batch(questions: List[Dict[str, Any]], batch_no: int = 1, thread_id: str = None) -> Dict[str, Any]:
    """
    Classify a batch of questions into learning topics AND extract key concepts
    being tested — all in a SINGLE LLM call.

    Returns:
        {
          "topics": [
            {
              "question_index": 0,
              "topic": "Graphs",
              "concepts": ["Shortest Path Property", "BFS Queue Usage", "Level-Order Traversal"]
            }
          ]
        }
    """
    if not questions:
        return {"topics": []}

    client = get_llm_client()
    model_name = getattr(client, "model", "unknown")

    system_prompt = (
    ''''
    You are an expert, domain-agnostic topic classifier and concept extractor.
Return ONLY valid JSON.
Do not return markdown.
Do not return code fences.
Do not return explanations.
Do not return plain text.
Your output must be valid JSON and parsable by json.loads().

Task:
For each question, perform TWO analyses:
1. Dynamically cluster it into ONE ultra-broad learning topic based on semantic similarity.
2. Extract the specific CONCEPTS being tested by the question.

Topic Classification Rules (Aggressive Macro-Clustering):
1. Definition of a Topic: A topic is a MACRO-LEVEL bucket equivalent to a broad "University Course Module" or "Textbook Chapter". 
2. Aggressive Consolidation: You must aggressively group related sub-topics, variants, and applications into single, unified buckets. 
   - BAD (Too Granular): "Algorithm Analysis", "Search Algorithms", "Sorting Algorithms" -> GOOD (Macro): "Algorithms & Complexity"
   - BAD (Too Granular): "Graph Algorithms", "Graph Representation", "Graphs" -> GOOD (Macro): "Graph Theory"
   - BAD (Too Granular): "Amplifier Circuits", "Power Amplifiers", "Amplifier Frequency Response" -> GOOD (Macro): "Amplifiers"
   - BAD (Too Granular): "Trees", "Binary Trees", "BST" -> GOOD (Macro): "Tree Data Structures"
3. Prevent Overlap: Before creating a new topic name, ask yourself: "Can this question fit into a broader topic I have already established or could establish?" If yes, use the broader topic. Do not split hairs.
4. Nomenclature: Use standard, high-level academic terminology. Avoid appending words like "Implementation," "Analysis," or "Representation" to the topic name unless absolutely necessary, as this causes unnecessary fragmentation.
5. Singularity & Consistency: Every question must belong to exactly ONE broad topic. If multiple themes intersect, choose the primary domain. Keep string names strictly consistent across similar questions.

Concept Extraction Rules:
1. Extract EXACTLY 1-2 core concepts that the question tests. Do not extract more than 2.
2. Concepts should be specific, granular, and testable (e.g., 'Bubble Sort Mechanism', not 'Algorithms').
3. Each concept should represent a distinct piece of knowledge required to answer correctly.
4. Include the primary concept being tested and any supporting concepts.
5. Concepts must inherently fall under the dynamically generated macro-topic.
6. Use clear, concise labels (2-5 words each).

CRITICAL SCOPE RULE:
You must ONLY extract concepts that are DIRECTLY tested by the given questions.
Do NOT infer, hallucinate, or add external concepts that are not explicitly present in the question text.
Every concept you list must be traceable to specific content in the question.

Concept Consolidation Rules (IMPORTANT):
1. Group similar or closely related concepts under a single consolidated parent concept name.
2. Examples of consolidation across domains:
   - 'Mitochondria function', 'Ribosome purpose' → 'Cellular Organelles'
   - 'Supply curves', 'Demand shifts' → 'Supply and Demand Dynamics'
   - 'Newton's First Law', 'Newton's Second Law' → 'Newtonian Mechanics'
   - 'Inorder Traversal', 'Postorder Traversal' → 'Tree Traversal'
3. The consolidated name should be broad enough to cover all grouped sub-concepts but specific enough for a questioning agent to generate targeted material.
4. Each question should produce 1 consolidated concept name, not individual sub-concepts.
        "Output Format:\n"
        "{\n"
        "  \"topics\": [\n"
        "    {\n"
        "      \"question_index\": 0,\n"
        "      \"topic\": \"Graphs\",\n"
        "      \"concepts\": [\"BFS Traversal Order\", \"Shortest Path Property\", \"Queue-Based Exploration\"]\n"
        "    }\n"
        "  ]\n"
        "}\n\n"

        "Strict Output Rules:\n"
        "* Return ONLY valid JSON.\n"
        "* Do NOT return markdown.\n"
        "* Do NOT return explanations.\n"
        "* Do NOT return code blocks.\n"
        "* Do NOT return question text.\n"
        "* Do NOT return options.\n"
        "* Do NOT return answers.\n"
        "* Do NOT return confidence scores.\n"
        "* Do NOT return any text before or after the JSON."
    '''
    )

    # Payload maps questions by their question_index
    payload = [
        {
            "question_index": idx,
            "question": item["question"]
        }
        for idx, item in enumerate(questions)
    ]

    prompt = (
        "Classify the following batch of questions into ONE broad learning topic each, "
        "and extract the specific concepts being tested by each question. "
        "Return ONLY valid JSON matching the schema.\n\n"
        f"Questions:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )

    max_retries = 5
    base_delay = 2.0

    for attempt in range(max_retries):
        try:
            response_text = client.generate_response(
                prompt=prompt,
                history=[],
                system_prompt=system_prompt,
                max_tokens=4096,
                thread_id=thread_id,
                agent_name="IngesterAgent"
            )

            parsed_response = parse_json_response(response_text, model_name=model_name, batch_no=batch_no)
            validate_llm_response(parsed_response)
            return parsed_response

        except Exception as e:
            if attempt == max_retries - 1:
                print(f"OpenRouter batch API call failed after {max_retries} attempts: {e}", file=sys.stderr)
                raise
            delay = base_delay * (2 ** attempt)
            print(f"OpenRouter batch API call failed: {e}. Retrying in {delay:.1f}s...", file=sys.stderr)
            time.sleep(delay)

    return {"topics": []}


def extract_concepts_only_batch(questions: List[Dict[str, Any]], batch_no: int = 1, thread_id: str = None) -> Dict[str, Any]:
    """
    Extract key concepts tested by questions that already have an assigned topic.

    Returns:
        {
          "topics": [
            {
              "question_index": 0,
              "concepts": ["Shortest Path Property", "BFS Queue Usage"]
            }
          ]
        }
    """
    if not questions:
        return {"topics": []}

    client = get_llm_client()
    model_name = getattr(client, "model", "unknown")

    system_prompt = (
    '''
    You are an expert, domain-agnostic concept extractor.
Return ONLY valid JSON.
Do not return markdown.
Do not return code fences.
Do not return explanations.
Do not return plain text.
Your output must be valid JSON and parsable by json.loads().

Task:
For each question, given its question text and assigned learning topic, extract the specific CONCEPTS being tested.

Concept Extraction Rules:
1. Extract EXACTLY 1-2 core concepts that the question tests. Do not extract more than 2.
2. Concepts should be specific, granular, and testable (e.g., 'Bubble Sort Mechanism', not 'Algorithms').
3. Each concept should represent a distinct piece of knowledge required to answer correctly.
4. Include the primary concept being tested and any supporting concepts.
5. Concepts must inherently fall under the assigned topic.
6. Use clear, concise labels (2-5 words each).

CRITICAL SCOPE RULE:
You must ONLY extract concepts that are DIRECTLY tested by the given questions.
Do NOT infer, hallucinate, or add external concepts that are not explicitly present in the question text.
Every concept you list must be traceable to specific content in the question.

Concept Consolidation Rules (IMPORTANT):
1. Group similar or closely related concepts under a single consolidated parent concept name.
2. Each question should produce 1-2 consolidated concept names.

Output Format:
{
  "topics": [
    {
      "question_index": 0,
      "concepts": ["BFS Traversal Order", "Shortest Path Property"]
    }
  ]
}

Strict Output Rules:
* Return ONLY valid JSON.
* Do NOT return markdown.
* Do NOT return explanations.
* Do NOT return code blocks.
* Do NOT return question text or options.
* Do NOT return answers.
* Do NOT return confidence scores.
* Do NOT return any text before or after the JSON.
    '''
    )

    payload = [
        {
            "question_index": idx,
            "topic": item.get("topic", "General"),
            "question": item["question"]
        }
        for idx, item in enumerate(questions)
    ]

    prompt = (
        "Extract the specific concepts tested by each of the following questions, "
        "given their assigned topic. Return ONLY valid JSON matching the schema.\n\n"
        f"Questions:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )

    max_retries = 5
    base_delay = 2.0

    for attempt in range(max_retries):
        try:
            response_text = client.generate_response(
                prompt=prompt,
                history=[],
                system_prompt=system_prompt,
                max_tokens=4096,
                thread_id=thread_id,
                agent_name="IngesterAgent"
            )

            parsed_response = parse_json_response(response_text, model_name=model_name, batch_no=batch_no)
            validate_llm_response(parsed_response, require_topic=False)
            return parsed_response

        except Exception as e:
            if attempt == max_retries - 1:
                print(f"OpenRouter batch API call failed after {max_retries} attempts: {e}", file=sys.stderr)
                raise
            delay = base_delay * (2 ** attempt)
            print(f"OpenRouter batch API call failed: {e}. Retrying in {delay:.1f}s...", file=sys.stderr)
            time.sleep(delay)

    return {"topics": []}


def process_csv(csv_path: str, classification_option: int = 1, thread_id: str = None) -> dict:
    """
    Reads the CSV, extracts question topics AND concepts (Option 1) or relies on CSV topics
    and extracts concepts (Option 2), compares user and correct answers, and groups statistics.

    Output format:
        {
          "topics": [
            {
              "topic": "Graphs",
              "no_of_questions": 3,
              "no_of_crt_ans": 2,
              "concepts": ["Shortest Path Property", "BFS Queue Usage", ...],
              "questions": [...]
            }
          ]
        }
    """
    try:
        classification_option = int(classification_option)
    except (ValueError, TypeError):
        classification_option = 1

    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Input CSV file not found at: {csv_path}")

    # Read CSV
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        raise ValueError(f"Failed to parse CSV file: {e}")

    # Validate required columns case-insensitively
    required_cols = ['Question', 'Correct_Answer', 'User_Answer']
    if classification_option == 2:
        required_cols.append('Topic')

    col_map = {}
    for req in required_cols:
        matched = None
        for col in df.columns:
            col_cleaned = col.strip().lower()
            req_cleaned = req.lower()
            if (
                col_cleaned == req_cleaned or
                col_cleaned.replace('_', ' ') == req_cleaned.replace('_', ' ') or
                col_cleaned.replace('_', '') == req_cleaned.replace('_', '')
            ):
                matched = col
                break
        if matched is None:
            if req == 'Topic':
                raise KeyError(
                    f"Missing required column: 'Topic' (required when Option 2 is selected). "
                    f"Available columns: {list(df.columns)}"
                )
            else:
                raise KeyError(
                    f"Missing required column: '{req}' (case-insensitive). "
                    f"Available columns: {list(df.columns)}"
                )
        col_map[req] = matched

    # Map option columns if they exist, case-insensitively
    opt_cols = ['Option_A', 'Option_B', 'Option_C', 'Option_D']
    opt_map = {}
    for i, opt in enumerate(opt_cols, start=1):
        matched = None
        for col in df.columns:
            col_cleaned = col.strip().lower()
            if col_cleaned in [
                opt.lower(),
                opt.lower().replace('_', ''),
                opt.lower().replace('_', ' '),
                f'op{i}',
                f'op_{i}',
                f'option{i}',
                f'option_{i}'
            ]:
                matched = col
                break
        opt_map[f'op{i}'] = matched

    # Prepare lists of cleaned inputs
    questions = [clean_str(x) for x in df[col_map['Question']].tolist()]
    correct_answers = [clean_str(x) for x in df[col_map['Correct_Answer']].tolist()]
    user_answers = [clean_str(x) for x in df[col_map['User_Answer']].tolist()]
    topics_from_csv = [clean_str(x) for x in df[col_map['Topic']].tolist()] if classification_option == 2 and 'Topic' in col_map else []

    opt_a_vals = [clean_str(x) for x in df[opt_map['op1']].tolist()] if opt_map['op1'] is not None else [""] * len(df)
    opt_b_vals = [clean_str(x) for x in df[opt_map['op2']].tolist()] if opt_map['op2'] is not None else [""] * len(df)
    opt_c_vals = [clean_str(x) for x in df[opt_map['op3']].tolist()] if opt_map['op3'] is not None else [""] * len(df)
    opt_d_vals = [clean_str(x) for x in df[opt_map['op4']].tolist()] if opt_map['op4'] is not None else [""] * len(df)

    # Reconstruct data locally for all questions
    original_questions = {}
    for idx in range(len(df)):
        q_num = idx + 1
        given_topic = topics_from_csv[idx] if (classification_option == 2 and idx < len(topics_from_csv) and topics_from_csv[idx]) else "Unclassified"
        original_questions[q_num] = {
            "question": questions[idx],
            "topic": given_topic,
            "op1": opt_a_vals[idx],
            "op2": opt_b_vals[idx],
            "op3": opt_c_vals[idx],
            "op4": opt_d_vals[idx],
            "correct_answer": correct_answers[idx],
            "user_answer": user_answers[idx],
            "is_correct": (correct_answers[idx] == user_answers[idx])
        }

    # Retrieve batch size configuration parameter
    batch_size_env = os.environ.get("BATCH_SIZE")
    try:
        batch_size = int(batch_size_env) if batch_size_env else 50
    except ValueError:
        batch_size = 50

    # Retrieve concurrency setting from env or default to 5
    max_workers_env = os.environ.get("MAX_WORKERS")
    try:
        max_workers = int(max_workers_env) if max_workers_env else 5
    except ValueError:
        max_workers = 5

    # Split questions into batches
    batches = []
    current_batch = []
    for q_num, info in original_questions.items():
        batch_item = {
            "question_no": q_num,
            "question": info["question"]
        }
        if classification_option == 2:
            batch_item["topic"] = info["topic"]
        current_batch.append(batch_item)

        if len(current_batch) == batch_size:
            batches.append(current_batch)
            current_batch = []
    if current_batch:
        batches.append(current_batch)

    assigned_topics = {}       # q_num -> topic_name
    assigned_concepts = {}     # q_num -> [concept_names]

    def process_batch(batch, batch_no):
        try:
            if classification_option == 2:
                result = extract_concepts_only_batch(batch, batch_no, thread_id=thread_id)
            else:
                result = classify_topics_batch(batch, batch_no, thread_id=thread_id)
            return batch, batch_no, result
        except Exception as e:
            print(f"Error processing batch {batch_no} starting with Q{batch[0]['question_no']}: {e}", file=sys.stderr)
            return batch, batch_no, {"topics": []}

    print(f"Processing {len(df)} questions (Option {classification_option}) in {len(batches)} batches using {max_workers} thread workers...")

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_batch = {
            executor.submit(process_batch, b, idx + 1): (b, idx + 1)
            for idx, b in enumerate(batches)
        }
        for future in concurrent.futures.as_completed(future_to_batch):
            batch, batch_no = future_to_batch[future]
            try:
                batch, batch_no, batch_response = future.result()
                batch_question_nos = [item["question_no"] for item in batch]

                for topic_info in batch_response.get("topics", []):
                    concepts = topic_info.get("concepts", [])
                    q_idx = topic_info.get("question_index")
                    try:
                        q_idx_int = int(q_idx)
                    except (ValueError, TypeError):
                        continue
                    # Ensure question_index is valid for the current batch
                    if 0 <= q_idx_int < len(batch):
                        q_no = batch[q_idx_int]["question_no"]
                        if classification_option == 2:
                            assigned_topics[q_no] = original_questions[q_no]["topic"]
                        else:
                            assigned_topics[q_no] = topic_info.get("topic", "Unclassified")
                        assigned_concepts[q_no] = concepts

                # Fallback any unclassified question numbers in this batch
                for q_no in batch_question_nos:
                    if q_no not in assigned_topics:
                        assigned_topics[q_no] = original_questions[q_no]["topic"] if classification_option == 2 else "Unclassified"
                    if q_no not in assigned_concepts:
                        assigned_concepts[q_no] = []
            except Exception as e:
                print(f"Critical error on batch {batch_no} starting with Q{batch[0]['question_no']}: {e}", file=sys.stderr)
                for item in batch:
                    q_no = item["question_no"]
                    if q_no not in assigned_topics:
                        assigned_topics[q_no] = original_questions[q_no]["topic"] if classification_option == 2 else "Unclassified"
                    if q_no not in assigned_concepts:
                        assigned_concepts[q_no] = []

    # Group by topic and build statistics
    topic_groups = defaultdict(list)
    topic_concepts = defaultdict(Counter)  # Count frequencies of concepts per topic

    for q_num, info in original_questions.items():
        topic = assigned_topics.get(q_num, "Unclassified")
        topic_groups[topic].append({
            "question": info["question"],
            "op1": info["op1"],
            "op2": info["op2"],
            "op3": info["op3"],
            "op4": info["op4"],
            "correct_answer": info["correct_answer"],
            "user_answer": info["user_answer"],
            "is_correct": info["is_correct"]
        })
        # Aggregate concepts for this topic
        for concept in assigned_concepts.get(q_num, []):
            if isinstance(concept, str) and concept.strip():
                topic_concepts[topic][concept.strip()] += 1

    topics_list = []
    for topic, q_list in topic_groups.items():
        no_of_questions = len(q_list)
        no_of_crt_ans = sum(1 for q in q_list if q["is_correct"])

        # Get top 5 concepts for this topic to limit interview length
        top_concepts = [c for c, count in topic_concepts.get(topic, Counter()).most_common(5)]

        # Filter: only pass correctly-answered MCQs downstream.
        # The questioning agent should only work with questions the student got right,
        # so it can verify understanding beyond rote recall.
        correct_only_questions = [q for q in q_list if q["is_correct"]]

        topics_list.append({
            "topic": topic,
            "no_of_questions": no_of_questions,
            "no_of_crt_ans": no_of_crt_ans,
            "concepts": sorted(top_concepts),
            "questions": correct_only_questions
        })

    # Sort topics alphabetically
    topics_list.sort(key=lambda x: x["topic"])

    return {"topics": topics_list}


def save_json(data: dict, output_path: str):
    """
    Saves the processed result dict as a JSON file.
    """
    try:
        out_dir = os.path.dirname(output_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        raise IOError(f"Failed to write output JSON to {output_path}: {e}")


def main():
    # Configuration variables for input, output, and concurrency
    input_csv = "test3.csv"
    output_json = "test3_output.json"
    workers = 1

    # Set concurrency limit via environment variable
    os.environ["MAX_WORKERS"] = str(workers)

    start_time = time.time()
    try:
        data = process_csv(input_csv)
        save_json(data, output_json)
        elapsed = time.time() - start_time
        print(f"Success! Processed results saved to {output_json} (took {elapsed:.2f}s)")
    except Exception as e:
        print(f"Execution Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
