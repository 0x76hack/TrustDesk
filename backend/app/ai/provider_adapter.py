from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, AsyncGenerator
from dataclasses import dataclass

@dataclass
class ModelResponse:
    content: str
    model_used: str
    token_usage: Dict[str, int]
    cost: Optional[float] = None
    finish_reason: str = 'stop'

@dataclass
class EmbeddingResponse:
    embeddings: List[List[float]]
    model_used: str
    token_usage: Dict[str, int]

class ProviderAdapter(ABC):
    @abstractmethod
    async def complete(
        self, messages: List[Dict[str, str]], model: str,
        temperature: float = 0.2, max_tokens: int = 2048,
        structured_output: Optional[Dict] = None
    ) -> ModelResponse: ...

    @abstractmethod
    async def complete_stream(
        self, messages: List[Dict[str, str]], model: str,
        temperature: float = 0.2, max_tokens: int = 2048
    ) -> AsyncGenerator[str, None]: ...

    @abstractmethod
    async def embed(self, texts: List[str], model: str) -> EmbeddingResponse: ...
