import json
import os
import time
import sys
from typing import Any, Dict, List
from ollama import Client as GenAIClient

from app.llms.openRouter import get_llm_logs_collection

class OllamaClient:
    """
    Ollama LLM Client conforming to the generate_response interface.
    """
    def __init__(self, host: str = "http://10.10.121.53:11434", model: str = "qwen2.5-coder:7b"):
        self.host = host
        self.model = os.environ.get("OLLAMA_MODEL", model)
        self.client = GenAIClient(host=self.host)

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
            else "You are a helpful AI assistant. Provide concise answers."
        )
        
        messages = [{"role": "system", "content": sys_content}]
        
        for msg in history:
            messages.append({"role": msg.get("role", "user"), "content": msg.get("content", "")})
            
        messages.append({"role": "user", "content": prompt})

        # We enforce basic JSON output format directly
        try:
            response = self.client.chat(
                model=self.model,
                messages=messages,
                format='json',
                options={
                    'temperature': 0.2
                }
            )
            
            text = response.get('message', {}).get('content', '').strip()
            
            # Map Ollama token counts to OpenRouter schema to keep logs dashboard working
            prompt_tokens = response.get("prompt_eval_count", 0)
            completion_tokens = response.get("eval_count", 0)
            usage = {
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "total_tokens": prompt_tokens + completion_tokens
            }
            
            if thread_id and agent_name:
                try:
                    get_llm_logs_collection().insert_one({
                        "thread_id": thread_id,
                        "agent": agent_name,
                        "model": f"ollama/{self.model}",
                        "messages": messages,
                        "response": text,
                        "usage": usage,
                        "timestamp": time.time()
                    })
                except Exception as e:
                    print(f"Failed to log LLM usage: {e}", file=sys.stderr)
                    
            return text
            
        except Exception as e:
            raise RuntimeError(f"Ollama API Error: {e}")
