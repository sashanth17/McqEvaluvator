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
from typing import List, Dict, Any, Generator
from collections import defaultdict
import pandas as pd
from dotenv import load_dotenv

load_dotenv()   



_mongo_client = None

def get_llm_logs_collection():
    global _mongo_client
    if _mongo_client is None:
        from pymongo import MongoClient
        mongo_uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
        _mongo_client = MongoClient(mongo_uri)
    return _mongo_client["mcq_evaluator"]["llm_logs"]

class OpenRouterClient:
    def __init__(self, api_key: str, model: str = "google/gemini-2.5-flash"):
        self.api_key = api_key
        self.model = model
        self.endpoint = "https://openrouter.ai/api/v1/chat/completions"

    def generate_response(
        self,
        prompt: str,
        history: List[Dict[str, Any]],
        system_prompt: str = None,
        max_tokens: int = 1024,
        thread_id: str = None,
        agent_name: str = None
    ) -> str:
        sys_content = (
            system_prompt 
            if system_prompt is not None 
            else "You are Shanks, a helpful AI coding assistant inside VS Code. Provide concise and helpful answers for developers."
        )
        
        messages = [{"role": "system", "content": sys_content}]
        
        for msg in history:
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
            
        messages.append({"role": "user", "content": prompt})

        data = json.dumps({
            "model": self.model,
            "stream": False,
            "messages": messages,
            "max_tokens" : max_tokens   
        }).encode('utf-8')

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        req = urllib.request.Request(self.endpoint, data=data, headers=headers, method="POST")
        context = ssl._create_unverified_context()

        try:
            with urllib.request.urlopen(req, context=context) as response:
                result = json.loads(response.read().decode('utf-8'))
                choices = result.get("choices", [])
                usage = result.get("usage", {})
                
                response_text = choices[0].get("message", {}).get("content", "") if choices else ""
                
                if thread_id and agent_name:
                    try:
                        print(f"[{agent_name}] Input Tokens: {usage.get('prompt_tokens', 0)} | Output Tokens: {usage.get('completion_tokens', 0)} | Total: {usage.get('total_tokens', 0)}")
                        get_llm_logs_collection().insert_one({
                            "thread_id": thread_id,
                            "agent": agent_name,
                            "model": self.model,
                            "messages": messages,
                            "response": response_text,
                            "usage": usage,
                            "timestamp": time.time()
                        })
                    except Exception as e:
                        print(f"Failed to log LLM usage: {e}", file=sys.stderr)
                        
                return response_text
        except urllib.error.HTTPError as e:
            err_body = e.read().decode('utf-8', errors='replace')
            raise RuntimeError(f"HTTP Error {e.code}: {e.reason} - {err_body}")
        except Exception as e:
            raise RuntimeError(str(e))

    def generate_streaming_response(
        self, 
        prompt: str, 
        history: List[Dict[str, Any]], 
        system_prompt: str = None,
        max_tokens: int = 1024
    ) -> Generator[str, None, None]:
        # Fallback system prompt if not customized
        sys_content = (
            system_prompt 
            if system_prompt is not None 
            else "You are Shanks, a helpful AI coding assistant inside VS Code. Provide concise and helpful answers for developers."
        )
        
        messages = [
            {
                "role": "system",
                "content": sys_content
                
            }
        ]

        
        for msg in history:
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
            
        messages.append({"role": "user", "content": prompt})

        data = json.dumps({
            "model": self.model,
            "stream": True,
            "messages": messages,
            "max_tokens" : max_tokens   
        }).encode('utf-8')

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        req = urllib.request.Request(self.endpoint, data=data, headers=headers, method="POST")

        # Bypass macOS SSL certificate verification error
        context = ssl._create_unverified_context()

        try:
            with urllib.request.urlopen(req, context=context) as response:
                for line in response:
                    line = line.decode('utf-8').strip()
                    if line.startswith("data: "):
                        content = line[6:]
                        if content == "[DONE]":
                            break
                        try:
                            parsed = json.loads(content)
                            choices = parsed.get("choices", [])
                            if choices:
                                delta = choices[0].get("delta", {})
                                chunk = delta.get("content", "")
                                if chunk:
                                    yield chunk
                        except json.JSONDecodeError:
                            continue
        except urllib.error.HTTPError as e:
            err_body = e.read().decode('utf-8', errors='replace')
            yield json.dumps({"error": f"HTTP Error {e.code}: {e.reason} - {err_body}"})
        except Exception as e:
            yield json.dumps({"error": str(e)})

# Global client holder for lazy initialization
_client = None

def get_openrouter_client() -> OpenRouterClient:
    """
    Lazily initializes and returns the OpenRouter client.
    Raises ValueError if API key is not set.
    """
    global _client
    if _client is None:
        api_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError(
                "API Key not found. Please set OPENROUTER_API_KEY or OPENAI_API_KEY environment variable. "
                "You can set it to 'mock' for local rule-based offline testing."
            )
        model = os.environ.get("OPENAI_MODEL") or os.environ.get("OPENROUTER_MODEL") or "google/gemini-2.5-flash"
        _client = OpenRouterClient(api_key=api_key, model=model)
    return _client

def clean_str(val) -> str:
    """
    Converts pandas value to clean stripped string.
    Handles NaN values by returning an empty string.
    """
    if pd.isna(val):
        return ""
    return str(val).strip()

def extract_topic(question: str) -> str:
    """
    Classify the topic of a given question using an LLM.
    Returns only the topic name (e.g. 'Binary Search', 'Queue').
    
    Supports offline mock mode if API key is 'mock'.
    """
    if not question.strip():
        return "Unclassified"

    api_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY")
    
    # Offline mock classifier for testing/dry-runs
    if api_key == "mock":
        q_lower = question.lower()
        if "binary search" in q_lower:
            return "Binary Search"
        elif "queue" in q_lower:
            return "Queue"
        elif "stack" in q_lower:
            return "Stack"
        elif "tree" in q_lower:
            return "Trees"
        elif "dynamic programming" in q_lower or "memoization" in q_lower:
            return "Dynamic Programming"
        elif "graph" in q_lower:
            return "Graphs"
        elif "quick sort" in q_lower or "sorting" in q_lower:
            return "Sorting"
        else:
            return "General CS"

    # Online API call using OpenRouterClient
    client = get_openrouter_client()
    system_prompt = (
       
    )
    
    max_retries = 5
    base_delay = 2.0  # seconds
    
    for attempt in range(max_retries):
        try:
            generator = client.generate_response(
                prompt=f"Question:\n{question}",
                history=[],
                system_prompt=system_prompt
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
                
            topic = "".join(chunks).strip().strip('"').strip("'").strip()
            return topic if topic else "Unclassified"
        except Exception as e:
            if attempt == max_retries - 1:
                print(f"OpenRouter API call failed after {max_retries} attempts: {e}", file=sys.stderr)
                raise
            delay = base_delay * (2 ** attempt)
            print(f"OpenRouter API call failed: {e}. Retrying in {delay:.1f}s...", file=sys.stderr)
            time.sleep(delay)
            
    return "Unclassified"