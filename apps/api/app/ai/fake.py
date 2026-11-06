"""Proveedor falso para pruebas: respuestas predefinidas, sin red ni modelo."""

import asyncio
from collections.abc import Callable

from app.ai.base import GenerationResult, LLMUnavailable, ProviderHealth, TokenCallback


class FakeProvider:
    name = "fake"

    def __init__(
        self,
        responses: list[str] | Callable[[str, str], str] | None = None,
        *,
        model: str = "fake-model",
        available: bool = True,
        token_delay: float = 0.0,
        tokens: int = 5,
    ):
        self.model = model
        self.available = available
        self.token_delay = token_delay
        self.tokens = tokens
        self._responses = responses if responses is not None else ["{}"]
        self.calls: list[dict] = []

    async def health(self) -> ProviderHealth:
        return ProviderHealth(
            available=self.available,
            provider=self.name,
            url="fake://",
            model=self.model,
            model_installed=self.available,
            version="0",
            models=[self.model] if self.available else [],
            error=None if self.available else "no disponible",
        )

    async def generate(
        self,
        system: str,
        prompt: str,
        *,
        schema: dict | None = None,
        max_tokens: int = 1024,
        on_token: TokenCallback | None = None,
    ) -> GenerationResult:
        if not self.available:
            raise LLMUnavailable("motor falso apagado")
        self.calls.append({"system": system, "prompt": prompt, "schema": schema})
        for i in range(1, self.tokens + 1):
            if self.token_delay:
                await asyncio.sleep(self.token_delay)
            if on_token:
                on_token(i)
        if callable(self._responses):
            text = self._responses(system, prompt)
        else:
            idx = min(len(self.calls) - 1, len(self._responses) - 1)
            text = self._responses[idx]
        return GenerationResult(text=text, prompt_tokens=10, output_tokens=self.tokens, total_seconds=1.0)
