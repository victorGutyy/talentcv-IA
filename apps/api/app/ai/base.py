"""Contrato del motor de IA. El resto de la aplicacion solo conoce esta interfaz,
de modo que Ollama pueda sustituirse por otro motor sin tocar los modulos."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


class LLMError(Exception):
    """Error generico del motor de IA."""


class LLMUnavailable(LLMError):
    """El motor no responde o el modelo no esta instalado."""


class LLMInvalidOutput(LLMError):
    """El modelo respondio algo que no cumple el esquema pedido."""


@dataclass
class ProviderHealth:
    available: bool
    provider: str
    url: str
    model: str
    model_installed: bool = False
    version: str | None = None
    models: list[str] = field(default_factory=list)
    error: str | None = None


@dataclass
class GenerationResult:
    text: str
    prompt_tokens: int = 0
    output_tokens: int = 0
    load_seconds: float = 0.0
    total_seconds: float = 0.0
    # Tiempo dedicado solo a generar (sin carga ni lectura del prompt), si el motor lo informa.
    generation_seconds: float = 0.0

    @property
    def tokens_per_second(self) -> float:
        gen = self.generation_seconds or (self.total_seconds - self.load_seconds)
        return self.output_tokens / gen if gen > 0 and self.output_tokens else 0.0


# Se llama con el numero de tokens generados hasta el momento.
TokenCallback = Callable[[int], None]


@runtime_checkable
class LLMProvider(Protocol):
    name: str
    model: str

    async def health(self) -> ProviderHealth: ...

    async def generate(
        self,
        system: str,
        prompt: str,
        *,
        schema: dict | None = None,
        max_tokens: int = 1024,
        on_token: TokenCallback | None = None,
    ) -> GenerationResult:
        """Genera texto. Con `schema` (JSON Schema) fuerza una salida JSON valida.

        Debe poder cancelarse: al cancelar la tarea asyncio se corta la generacion.
        """
        ...
