"""Adaptador de Ollama (solo localhost, sin telemetria)."""

import json
import time

import httpx

from app.ai.base import (
    GenerationResult,
    LLMError,
    LLMUnavailable,
    ProviderHealth,
    TokenCallback,
)
from app.core.config import Settings


class OllamaProvider:
    name = "ollama"

    def __init__(self, settings: Settings, *, transport: httpx.AsyncBaseTransport | None = None):
        self.url = settings.ollama_url.rstrip("/")
        self.model = settings.model
        self.num_ctx = settings.num_ctx
        # Sin proxies ni variables de entorno: nada debe desviar el trafico fuera del equipo.
        self._client = httpx.AsyncClient(
            base_url=self.url,
            timeout=httpx.Timeout(connect=3.0, read=300.0, write=30.0, pool=5.0),
            trust_env=False,
            transport=transport,
        )

    async def aclose(self) -> None:
        await self._client.aclose()

    async def health(self) -> ProviderHealth:
        base = ProviderHealth(available=False, provider=self.name, url=self.url, model=self.model)
        try:
            version = (await self._client.get("/api/version", timeout=3.0)).json().get("version")
            tags = (await self._client.get("/api/tags", timeout=5.0)).json()
        except (httpx.HTTPError, ValueError) as e:
            base.error = f"No se pudo conectar con Ollama en {self.url}: {type(e).__name__}"
            return base
        models = sorted(m.get("name", "") for m in tags.get("models", []))
        base.available = True
        base.version = version
        base.models = models
        base.model_installed = self.model in models
        if not base.model_installed:
            base.error = f"El modelo «{self.model}» no está instalado."
        return base

    async def generate(
        self,
        system: str,
        prompt: str,
        *,
        schema: dict | None = None,
        max_tokens: int = 1024,
        on_token: TokenCallback | None = None,
    ) -> GenerationResult:
        body: dict = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt},
            ],
            "stream": True,
            "options": {"temperature": 0, "num_ctx": self.num_ctx, "num_predict": max_tokens},
            "keep_alive": "5m",
        }
        if schema is not None:
            body["format"] = schema

        started = time.perf_counter()
        parts: list[str] = []
        final: dict = {}
        count = 0
        try:
            async with self._client.stream("POST", "/api/chat", json=body) as resp:
                if resp.status_code != 200:
                    detail = (await resp.aread()).decode("utf-8", "replace")[:300]
                    try:
                        detail = json.loads(detail).get("error", detail)
                    except ValueError:
                        pass
                    raise LLMUnavailable(f"Ollama respondió {resp.status_code}: {detail}")
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    chunk = json.loads(line)
                    if "error" in chunk:
                        raise LLMError(f"Ollama: {chunk['error']}")
                    piece = chunk.get("message", {}).get("content", "")
                    if piece:
                        parts.append(piece)
                        count += 1  # un fragmento ~ un token
                        if on_token:
                            on_token(count)
                    if chunk.get("done"):
                        final = chunk
        except httpx.ConnectError as e:
            raise LLMUnavailable(f"No se pudo conectar con Ollama en {self.url}.") from e
        except httpx.ReadTimeout as e:
            raise LLMError("Ollama tardó demasiado en responder.") from e
        except httpx.HTTPError as e:
            raise LLMError(f"Fallo de comunicación con Ollama: {type(e).__name__}") from e

        return GenerationResult(
            text="".join(parts),
            prompt_tokens=int(final.get("prompt_eval_count", 0)),
            output_tokens=int(final.get("eval_count", count)),
            load_seconds=final.get("load_duration", 0) / 1e9,
            total_seconds=time.perf_counter() - started,
            generation_seconds=final.get("eval_duration", 0) / 1e9,
        )
