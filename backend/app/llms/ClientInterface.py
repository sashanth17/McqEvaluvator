from abc import ABC, abstractmethod
from typing import List, Dict, Any, Generator

class IAIClient(ABC):
    """
    Abstract Base Class for AI Clients in Python.
    Designed to mirror the extensibility of the voice agent.
    """
    
    @abstractmethod
    def generate_streaming_response(self, prompt: str, history: List[Dict[str, Any]]) -> Generator[str, None, None]:
        """
        Generates a streaming response string chunk by chunk.
        
        Args:
            prompt: The user prompt.
            history: List of previous messages, e.g., [{"role": "user", "content": "..."}]
            
        Yields:
            str: Chunks of the generated response.
        """
        yield ''