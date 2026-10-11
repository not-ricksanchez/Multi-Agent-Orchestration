import json
from io import BytesIO

import pytest

from underwriting.models import (
    ModelResult,
    OllamaModelAdapter,
    ScriptedModelAdapter,
)


def test_scripted_adapter_returns_results_and_records_prompts():
    first = ModelResult(
        content={"section": "intake"},
        model="scripted",
        input_tokens=10,
        output_tokens=4,
    )
    second = ModelResult(
        content={"section": "enrichment"},
        model="scripted",
        input_tokens=12,
        output_tokens=6,
    )
    adapter = ScriptedModelAdapter([first, second])

    assert adapter.complete("system-a", "user sees intake") == first
    assert adapter.complete("system-b", "user sees enrichment") == second
    assert adapter.prompts == [
        ("system-a", "user sees intake"),
        ("system-b", "user sees enrichment"),
    ]


def test_ollama_adapter_posts_chat_and_parses_json_content(monkeypatch):
    captured = {}

    class FakeResponse(BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(request, timeout=None):
        captured["url"] = request.full_url
        captured["method"] = request.get_method()
        captured["body"] = json.loads(request.data.decode())
        payload = {
            "message": {"role": "assistant", "content": '{"decision": "approve"}'},
            "prompt_eval_count": 120,
            "eval_count": 30,
        }
        return FakeResponse(json.dumps(payload).encode())

    monkeypatch.setattr("underwriting.models.urlopen", fake_urlopen)
    adapter = OllamaModelAdapter(base_url="http://ollama.test")

    result = adapter.complete("be precise", "application text")

    assert result == ModelResult(
        content={"decision": "approve"},
        model="gemma3:12b",
        input_tokens=120,
        output_tokens=30,
    )
    assert captured["url"] == "http://ollama.test/api/chat"
    assert captured["method"] == "POST"
    assert captured["body"] == {
        "model": "gemma3:12b",
        "stream": False,
        "format": "json",
        "options": {"temperature": 0},
        "messages": [
            {"role": "system", "content": "be precise"},
            {"role": "user", "content": "application text"},
        ],
    }


def test_ollama_adapter_uses_ollama_base_url_when_base_url_is_omitted(monkeypatch):
    captured = {}

    class FakeResponse(BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(request, timeout=None):
        captured["url"] = request.full_url
        payload = {
            "message": {"content": "{}"},
            "prompt_eval_count": 1,
            "eval_count": 1,
        }
        return FakeResponse(json.dumps(payload).encode())

    monkeypatch.setenv("OLLAMA_BASE_URL", "http://host.docker.internal:11434")
    monkeypatch.setattr("underwriting.models.urlopen", fake_urlopen)

    OllamaModelAdapter().complete("system", "user")

    assert captured["url"] == "http://host.docker.internal:11434/api/chat"


def test_ollama_adapter_raises_value_error_on_non_json_content(monkeypatch):
    class FakeResponse(BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def fake_urlopen(request, timeout=None):
        payload = {
            "message": {"role": "assistant", "content": "not json"},
            "prompt_eval_count": 5,
            "eval_count": 2,
        }
        return FakeResponse(json.dumps(payload).encode())

    monkeypatch.setattr("underwriting.models.urlopen", fake_urlopen)
    adapter = OllamaModelAdapter(base_url="http://ollama.test")

    with pytest.raises(ValueError):
        adapter.complete("system", "user")
