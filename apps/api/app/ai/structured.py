"""Salida estructurada: JSON validado con Pydantic, con un reintento guiado."""

from typing import TypeVar

from pydantic import BaseModel, ValidationError

from app.ai.base import GenerationResult, LLMInvalidOutput, LLMProvider, TokenCallback

T = TypeVar("T", bound=BaseModel)


def strict_schema(model_cls: type[BaseModel]) -> dict:
    """JSON Schema en modo estricto para el motor de IA.

    Pydantic marca como opcionales los campos con valor por defecto; en ese caso el
    modelo local puede cerrar el JSON tras el primer campo (medido con qwen3:4b-instruct:
    devolvia solo «nombre»). Exigimos todos los campos y prohibimos los extras; un dato
    ausente debe expresarse con null, nunca omitiendose.
    """

    def endurecer(node):
        if isinstance(node, dict):
            if node.get("type") == "object" and "properties" in node:
                node["required"] = list(node["properties"])
                node["additionalProperties"] = False
            for v in node.values():
                endurecer(v)
        elif isinstance(node, list):
            for v in node:
                endurecer(v)

    schema = model_cls.model_json_schema()
    endurecer(schema)
    return schema


async def generate_structured(
    provider: LLMProvider,
    model_cls: type[T],
    system: str,
    prompt: str,
    *,
    max_tokens: int = 1024,
    on_token: TokenCallback | None = None,
    retries: int = 1,
) -> tuple[T, GenerationResult]:
    """Pide JSON conforme a `model_cls`. Si no valida, reintenta una vez indicando el error."""
    schema = strict_schema(model_cls)
    current = prompt
    last_error = ""
    for _ in range(retries + 1):
        result = await provider.generate(
            system, current, schema=schema, max_tokens=max_tokens, on_token=on_token
        )
        try:
            return model_cls.model_validate_json(result.text), result
        except ValidationError as e:
            last_error = "; ".join(f"{'.'.join(map(str, x['loc']))}: {x['msg']}" for x in e.errors()[:5])
            current = (
                f"{prompt}\n\nTu respuesta anterior no cumplió el formato ({last_error}). "
                "Responde de nuevo solo con JSON válido según el esquema."
            )
    raise LLMInvalidOutput(f"El modelo no produjo una salida válida: {last_error}")
