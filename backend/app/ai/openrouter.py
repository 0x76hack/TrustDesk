import json
import asyncio
from typing import Optional, List, Dict, Any, AsyncGenerator
import httpx
from .provider_adapter import ProviderAdapter, ModelResponse, EmbeddingResponse

class OpenRouterError(Exception):
    pass

class OpenRouterProvider(ProviderAdapter):
    def __init__(self, api_key: str, base_url: str = "https://openrouter.ai/api/v1"):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "HTTP-Referer": "https://trustdesk.ai",
            "X-Title": "TrustDesk",
        }
        self.timeout = httpx.Timeout(30.0)
        self._client = httpx.AsyncClient(
            headers=self.headers,
            timeout=self.timeout,
            limits=httpx.Limits(max_connections=50, max_keepalive_connections=20),
        )

    async def aclose(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    async def _retry_request(self, method: str, url: str, **kwargs) -> httpx.Response:
        if not self.api_key or not self.api_key.strip():
            raise OpenRouterError("OpenRouter API key is not configured")
        retries = 3
        base_delay = 1.0
        for attempt in range(retries):
            try:
                response = await self._client.request(method, url, **kwargs)
                response.raise_for_status()
                return response
            except httpx.HTTPStatusError as e:
                if e.response.status_code in (400, 401, 403, 404):
                    raise OpenRouterError(f"HTTP {e.response.status_code}: {e.response.text}")
                if attempt == retries - 1:
                    raise OpenRouterError(f"Request failed after {retries} attempts: {e}")
                await asyncio.sleep(base_delay * (2 ** attempt))
            except httpx.RequestError as e:
                if attempt == retries - 1:
                    raise OpenRouterError(f"Request failed after {retries} attempts: {e}")
                await asyncio.sleep(base_delay * (2 ** attempt))
        raise OpenRouterError("Unexpected error")

    async def complete(
        self, messages: List[Dict[str, str]], model: str,
        temperature: float = 0.2, max_tokens: int = 2048,
        structured_output: Optional[Dict] = None
    ) -> ModelResponse:
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }
        if structured_output:
            payload["response_format"] = {"type": "json_object"}

        response = await self._retry_request("POST", url, json=payload)
        data = response.json()

        choice = data['choices'][0]
        return ModelResponse(
            content=choice['message']['content'],
            model_used=data['model'],
            token_usage=data.get('usage', {}),
            finish_reason=choice.get('finish_reason', 'stop')
        )

    async def complete_stream(
        self, messages: List[Dict[str, str]], model: str,
        temperature: float = 0.2, max_tokens: int = 2048
    ) -> AsyncGenerator[str, None]:
        url = f"{self.base_url}/chat/completions"
        payload = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True
        }

        async with self._client.stream("POST", url, json=payload) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    line = line[6:]
                    if line == "[DONE]":
                        break
                    try:
                        chunk = json.loads(line)
                        delta = chunk['choices'][0].get('delta', {})
                        if 'content' in delta:
                            yield delta['content']
                    except json.JSONDecodeError:
                        pass

    async def embed(self, texts: List[str], model: str) -> EmbeddingResponse:
        from .embedding_utils import generate_dense_embedding
        if not self.api_key or not self.api_key.strip():
            return EmbeddingResponse(
                embeddings=[generate_dense_embedding(t) for t in texts],
                model_used="dense-embedding-fallback",
                token_usage={"prompt_tokens": len(" ".join(texts).split()), "total_tokens": len(" ".join(texts).split())}
            )

        url = f"{self.base_url}/embeddings"
        payload = {
            "model": model,
            "input": texts,
        }

        try:
            response = await self._retry_request("POST", url, json=payload)
            data = response.json()
            embeddings = [item['embedding'] for item in data['data']]
            return EmbeddingResponse(
                embeddings=embeddings,
                model_used=data['model'],
                token_usage=data.get('usage', {})
            )
        except OpenRouterError:
            return EmbeddingResponse(
                embeddings=[generate_dense_embedding(t) for t in texts],
                model_used="dense-embedding-fallback",
                token_usage={"prompt_tokens": len(" ".join(texts).split()), "total_tokens": len(" ".join(texts).split())}
            )
