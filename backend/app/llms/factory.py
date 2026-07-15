import os
import sys

from app.llms.openRouter import OpenRouterClient

_client = None

def get_llm_client():
    """
    Returns the LLM client based on the LLM_PROVIDER environment variable.
    Defaults to OpenRouterClient if not set or set to 'openrouter'.
    """
    global _client
    if _client is not None:
        return _client

    provider = os.environ.get("LLM_PROVIDER", "openrouter").lower()

    if provider == "ollama":
        from app.llms.ollamaClient import OllamaClient
        print("Initializing OllamaClient...", file=sys.stderr)
        _client = OllamaClient()
    else:
        api_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("API Key not found for OpenRouter. Please set OPENROUTER_API_KEY.")
        model = os.environ.get("OPENAI_MODEL") or os.environ.get("OPENROUTER_MODEL") or "google/gemini-2.5-flash"
        print(f"Initializing OpenRouterClient with model: {model}...", file=sys.stderr)
        _client = OpenRouterClient(api_key=api_key, model=model)

    return _client
