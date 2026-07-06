#!/usr/bin/env python3
"""
Topic Parser Script
Classifies question topics in a CSV file using OpenRouter, groups them,
calculates performance statistics, and exports the result to JSON.
"""

import os
import sys
import json
import time
import concurrent.futures
import urllib.request
import ssl
import re
from typing import List, Dict, Any, Generator
from collections import defaultdict
import pandas as pd
from dotenv import load_dotenv

load_dotenv()   

print("API Key:", os.getenv("OPENROUTER_API_KEY"))


from app.llms.openRouter import OpenRouterClient, get_openrouter_client

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
                        "topic": json_str
                    }
                ]
            }
        else:
            # It starts with JSON brackets/braces but is malformed JSON; log raw response and raise a descriptive error
            print(f"JSON parsing failed on malformed JSON: {e}", file=sys.stderr)
            raise ValueError(f"Failed to decode response as JSON (malformed JSON structure): {e}. Raw response: {text}")

def validate_llm_response(data: Any) -> None:
    """
    Validates that the response dict conforms to the expected question_index schema.
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
        if "topic" not in item:
            raise ValueError(f"Validation Error: Topic item at index {idx} is missing the 'topic' key.")
        
        # Verify that question_index is/can be an integer
        try:
            int(item["question_index"])
        except (ValueError, TypeError):
            raise ValueError(f"Validation Error: 'question_index' at index {idx} must be an integer, got {item['question_index']}")

def classify_topics_batch(questions: List[Dict[str, Any]], batch_no: int = 1) -> Dict[str, Any]:
    """
    Classify a batch of questions into learning topics using an LLM.
    
    questions is a list of:
    [
      {"question_no": 1, "question": "..."},
      ...
    ]
    
    Returns a dictionary matching:
    {
      "topics": [
        {"question_index": 0, "topic": "Arrays"}
      ]
    }
    """
    if not questions:
        return {"topics": []}
        
    api_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY")
    
    # Offline mock classifier for testing/dry-runs
    # if api_key == "mock":
    #     topic_items = []
    #     for idx, q_item in enumerate(questions):
    #         q_text = q_item["question"]
    #         if not q_text.strip():
    #             topic = "Unclassified"
    #         else:
    #             q_lower = q_text.lower()
    #             if "binary search" in q_lower:
    #                 topic = "Searching"
    #             elif "queue" in q_lower:
    #                 topic = "Queue"
    #             elif "stack" in q_lower:
    #                 topic = "Stack"
    #             elif "tree" in q_lower:
    #                 topic = "Trees"
    #             elif "dynamic programming" in q_lower or "memoization" in q_lower:
    #                 topic = "Dynamic Programming"
    #             elif "graph" in q_lower:
    #                 topic = "Graphs"
    #             elif "quick sort" in q_lower or "sorting" in q_lower:
    #                 topic = "Sorting"
    #             elif "array" in q_lower:
    #                 topic = "Arrays"
    #             elif "linked list" in q_lower:
    #                 topic = "Linked List"
    #             else:
    #                 topic = "General CS"
    #         topic_items.append({
    #             "question_index": idx,
    #             "topic": topic
    #         })
            
        # return {"topics": topic_items}
        
    client = get_openrouter_client()
    model_name = client.model
    
    system_prompt = (
        "You are an expert topic classifier.\n"
        "Return ONLY valid JSON.\n"
        "Do not return markdown.\n"
        "Do not return code fences.\n"
        "Do not return explanations.\n"
        "Do not return plain text.\n"
        "Your output must be valid JSON and parsable by json.loads().\n\n"
        "Task:\n"
        "Analyze each question and classify it into ONE broad learning topic from the approved taxonomy.\n"
        "Your objective is to identify the primary subject area being tested and group questions that belong to the same learning topic.\n\n"
        "Classification Rules:\n"
        "1. Every question must belong to exactly ONE topic.\n"
        "2. Classify based on the core knowledge required to answer the question.\n"
        "3. Do NOT classify based on surface keywords alone.\n"
        "4. Map specific algorithms, formulas, techniques, protocols, operations, commands, theorems, laws, and concepts to their parent learning topic.\n"
        "5. If multiple topics appear, choose the topic most essential for solving the question.\n"
        "6. Use ONLY topics from the approved taxonomy.\n"
        "7. Never create new topic names.\n"
        "8. Return only valid JSON.\n\n"
        "Approved Taxonomy:\n"
        "Data Structures and Algorithms:\n"
        "* Arrays, Linked List, Stack, Queue, Trees, Graphs, Hashing, Searching, Sorting, Dynamic Programming, Greedy Algorithms, Backtracking, Recursion, Strings, Bit Manipulation\n\n"
        "Core Computer Science:\n"
        "* Operating Systems, DBMS, Computer Networks, Compiler Design, Computer Organization and Architecture, Theory of Computation, Software Engineering, Object Oriented Programming\n\n"
        "Artificial Intelligence and Data Science:\n"
        "* Artificial Intelligence, Machine Learning, Deep Learning, Data Science\n\n"
        "Programming:\n"
        "* C Programming, C++, Java, Python, JavaScript\n\n"
        "Mathematics:\n"
        "* Discrete Mathematics, Linear Algebra, Calculus, Probability and Statistics\n\n"
        "Cyber Security:\n"
        "* Cyber Security\n\n"
        "Aptitude:\n"
        "* Aptitude - Quantitative Aptitude, Aptitude - Logical Reasoning, Aptitude - Verbal Ability, Aptitude - Probability\n\n"
        "Mapping Examples:\n"
        "BFS, DFS, Dijkstra, Bellman-Ford, Floyd Warshall, Topological Sort, MST, Connected Components -> Graphs\n"
        "AVL Tree, BST, Red Black Tree, Heap, Segment Tree, Fenwick Tree -> Trees\n"
        "Linear Search, Binary Search, Lower Bound, Upper Bound -> Searching\n"
        "Merge Sort, Quick Sort, Heap Sort, Counting Sort, Radix Sort -> Sorting\n"
        "Knapsack, LCS, LIS, Matrix Chain Multiplication -> Dynamic Programming\n"
        "Array Rotation, Prefix Sum, Sliding Window, Kadane Algorithm -> Arrays\n"
        "Stack Operations, Parenthesis Matching, Expression Evaluation -> Stack\n"
        "Queue, Circular Queue, Deque, Priority Queue -> Queue\n"
        "Deadlock, Scheduling, Paging, Virtual Memory -> Operating Systems\n"
        "Normalization, SQL, Transactions, ACID, Indexing -> DBMS\n"
        "TCP, UDP, DNS, Routing, HTTP, Congestion Control -> Computer Networks\n"
        "Lexical Analysis, Parsing, Syntax Trees -> Compiler Design\n"
        "RSA, AES, Authentication, Authorization, Cryptography -> Cyber Security\n"
        "Bayes Theorem, Conditional Probability, Permutation, Combination -> Aptitude - Probability\n\n"
        "Output Format:\n"
        "{\n"
        "  \"topics\": [\n"
        "    {\n"
        "      \"question_index\": 0,\n"
        "      \"topic\": \"Arrays\"\n"
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
        "Classify the following batch of questions into ONE broad learning topic each. "
        "Return ONLY valid JSON matching the schema.\n\n"
        f"Questions:\n{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )
    
    max_retries = 5
    base_delay = 2.0
    
    for attempt in range(max_retries):
        try:
            generator = client.generate_streaming_response(
                prompt=prompt,
                history=[],
                system_prompt=system_prompt,
                max_tokens=4096
            )
            
            chunks = []
            for chunk in generator:
                if chunk.startswith('{"error":'):
                    try:
                        err_dict = json.loads(chunk)
                        raise RuntimeError(err_dict.get("error", "Unknown API error"))
                    except json.JSONDecodeError:
                        pass
                chunks.append(chunk)
                
            response_text = "".join(chunks).strip()
            
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


def process_csv(csv_path: str) -> dict:
    """
    Reads the CSV, extracts question topics concurrently,
    compares user and correct answers, and groups the statistics.
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"Input CSV file not found at: {csv_path}")

    # Read CSV
    try:
        df = pd.read_csv(csv_path)
    except Exception as e:
        raise ValueError(f"Failed to parse CSV file: {e}")

    # Validate required columns case-insensitively
    required_cols = ['Question', 'Correct_Answer', 'User_Answer']
    col_map = {}
    for req in required_cols:
        matched = None
        for col in df.columns:
            if col.strip().lower() == req.lower():
                matched = col
                break
        if matched is None:
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
    
    opt_a_vals = [clean_str(x) for x in df[opt_map['op1']].tolist()] if opt_map['op1'] is not None else [""] * len(df)
    opt_b_vals = [clean_str(x) for x in df[opt_map['op2']].tolist()] if opt_map['op2'] is not None else [""] * len(df)
    opt_c_vals = [clean_str(x) for x in df[opt_map['op3']].tolist()] if opt_map['op3'] is not None else [""] * len(df)
    opt_d_vals = [clean_str(x) for x in df[opt_map['op4']].tolist()] if opt_map['op4'] is not None else [""] * len(df)

    # Reconstruct data locally for all questions
    original_questions = {}
    for idx in range(len(df)):
        q_num = idx + 1
        original_questions[q_num] = {
            "question": questions[idx],
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
        current_batch.append({
            "question_no": q_num,
            "question": info["question"]
        })
        if len(current_batch) == batch_size:
            batches.append(current_batch)
            current_batch = []
    if current_batch:
        batches.append(current_batch)

    assigned_topics = {}

    def process_batch(batch, batch_no):
        try:
            result = classify_topics_batch(batch, batch_no)
            return batch, batch_no, result
        except Exception as e:
            print(f"Error processing batch {batch_no} starting with Q{batch[0]['question_no']}: {e}", file=sys.stderr)
            return batch, batch_no, {"topics": []}

    print(f"Processing {len(df)} questions in {len(batches)} batches using {max_workers} thread workers...")
    
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
                    topic_name = topic_info.get("topic", "Unclassified")
                    q_idx = topic_info.get("question_index")
                    try:
                        q_idx_int = int(q_idx)
                    except (ValueError, TypeError):
                        continue
                    # Ensure question_index is valid for the current batch
                    if 0 <= q_idx_int < len(batch):
                        q_no = batch[q_idx_int]["question_no"]
                        assigned_topics[q_no] = topic_name
                            
                # Fallback any unclassified question numbers in this batch
                for q_no in batch_question_nos:
                    if q_no not in assigned_topics:
                        assigned_topics[q_no] = "Unclassified"
            except Exception as e:
                print(f"Critical error on batch {batch_no} starting with Q{batch[0]['question_no']}: {e}", file=sys.stderr)
                for item in batch:
                    q_no = item["question_no"]
                    if q_no not in assigned_topics:
                        assigned_topics[q_no] = "Unclassified"

    # Group by topic and build statistics
    topic_groups = defaultdict(list)
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

    topics_list = []
    for topic, q_list in topic_groups.items():
        no_of_questions = len(q_list)
        no_of_crt_ans = sum(1 for q in q_list if q["is_correct"])
        
        topics_list.append({
            "topic": topic,
            "no_of_questions": no_of_questions,
            "no_of_crt_ans": no_of_crt_ans,
            "questions": q_list
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
