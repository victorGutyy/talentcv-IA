import json

import httpx
import pytest

from app.ai.base import LLMError, LLMUnavailable
from app.ai.ollama import OllamaProvider
from app.core.config import ConfigError, Settings

pytestmark = pytest.mark.anyio


def _settings(tmp_path):
    return Settings(data_dir=tmp_path, token="t")


def _ndjson(*chunks: dict) -> bytes:
    return ("\n".join(json.dumps(c) for c in chunks) + "\n").encode()


def _provider(tmp_path, handler):
    return OllamaProvider(_settings(tmp_path), transport=httpx.MockTransport(handler))


async def test_health_disponible_con_modelo(tmp_path):
    def handler(req):
        if req.url.path == "/api/version":
            return httpx.Response(200, json={"version": "0.40.14"})
        return httpx.Response(200, json={"models": [{"name": "qwen3:4b-instruct"}, {"name": "otro:1b"}]})

    p = _provider(tmp_path, handler)
    h = await p.health()
    assert h.available and h.model_installed and h.version == "0.40.14"
    assert h.models == ["otro:1b", "qwen3:4b-instruct"]
    assert h.error is None


async def test_health_modelo_no_instalado(tmp_path):
    def handler(req):
        if req.url.path == "/api/version":
            return httpx.Response(200, json={"version": "1"})
        return httpx.Response(200, json={"models": [{"name": "otro:1b"}]})

    h = await _provider(tmp_path, handler).health()
    assert h.available and not h.model_installed
    assert "no está instalado" in h.error


async def test_health_sin_conexion(tmp_path):
    def handler(req):
        raise httpx.ConnectError("rechazado")

    h = await _provider(tmp_path, handler).health()
    assert not h.available and "No se pudo conectar" in h.error


async def test_generate_acumula_texto_y_estadisticas(tmp_path):
    visto = {}

    def handler(req):
        visto.update(json.loads(req.content))
        return httpx.Response(
            200,
            content=_ndjson(
                {"message": {"content": '{"a":'}, "done": False},
                {"message": {"content": " 1}"}, "done": False},
                {
                    "message": {"content": ""},
                    "done": True,
                    "eval_count": 2,
                    "prompt_eval_count": 7,
                    "load_duration": 2_000_000_000,
                },
            ),
        )

    progreso = []
    r = await _provider(tmp_path, handler).generate(
        "sistema", "pregunta", schema={"type": "object"}, on_token=progreso.append
    )
    assert r.text == '{"a": 1}'
    assert (r.prompt_tokens, r.output_tokens) == (7, 2)
    assert r.load_seconds == 2.0
    assert progreso == [1, 2]
    # parametros enviados al modelo
    assert visto["model"] == "qwen3:4b-instruct"
    assert visto["format"] == {"type": "object"}
    assert visto["options"]["temperature"] == 0
    assert visto["stream"] is True
    assert [m["role"] for m in visto["messages"]] == ["system", "user"]


async def test_generate_modelo_inexistente(tmp_path):
    def handler(req):
        return httpx.Response(404, json={"error": "model 'x' not found"})

    with pytest.raises(LLMUnavailable, match="not found"):
        await _provider(tmp_path, handler).generate("s", "p")


async def test_generate_error_en_el_flujo(tmp_path):
    def handler(req):
        return httpx.Response(200, content=_ndjson({"error": "sin memoria"}))

    with pytest.raises(LLMError, match="sin memoria"):
        await _provider(tmp_path, handler).generate("s", "p")


async def test_generate_sin_conexion(tmp_path):
    def handler(req):
        raise httpx.ConnectError("rechazado")

    with pytest.raises(LLMUnavailable):
        await _provider(tmp_path, handler).generate("s", "p")


@pytest.mark.parametrize(
    "url",
    [
        "http://ollama.example.com:11434",
        "http://192.168.1.10:11434",
        "https://127.0.0.1:11434",
        "http://0.0.0.0:11434",
    ],
)
def test_rechaza_motores_de_ia_que_no_son_locales(tmp_path, url):
    with pytest.raises(ConfigError):
        Settings(data_dir=tmp_path, ollama_url=url)


@pytest.mark.parametrize("url", ["http://127.0.0.1:11434", "http://localhost:11434"])
def test_acepta_urls_locales(tmp_path, url):
    assert Settings(data_dir=tmp_path, ollama_url=url).ollama_url == url


def test_el_cliente_ignora_proxies_del_entorno(tmp_path, monkeypatch):
    monkeypatch.setenv("HTTP_PROXY", "http://proxy.externo:3128")
    p = OllamaProvider(_settings(tmp_path))
    assert p._client._trust_env is False
