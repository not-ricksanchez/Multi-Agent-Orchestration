import json
import os
from dataclasses import dataclass
from typing import Protocol
from urllib.request import Request, urlopen


@dataclass(frozen=True)
class ModelResult:
    content: dict
    model: str
    input_tokens: int
    output_tokens: int


class ModelAdapter(Protocol):
    def complete(self, system: str, user: str) -> ModelResult: ...


class ScriptedModelAdapter:
    def __init__(self, results: list[ModelResult]):
        self._results = list(results)
        self.prompts: list[tuple[str, str]] = []

    def complete(self, system: str, user: str) -> ModelResult:
        self.prompts.append((system, user))
        return self._results.pop(0)


class OllamaModelAdapter:
    def __init__(self, base_url: str | None = None, model: str = "gemma3:12b"):
        if base_url is None:
            base_url = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        self.base_url = base_url.rstrip("/")
        self.model = model

    def complete(self, system: str, user: str) -> ModelResult:
        payload = {
            "model": self.model,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        request = Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(request) as response:
            body = _json_object(response.read().decode())
        content = _json_object(body["message"]["content"])
        return ModelResult(
            content=content,
            model=self.model,
            input_tokens=body["prompt_eval_count"],
            output_tokens=body["eval_count"],
        )


def _json_object(text: str) -> dict:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ValueError("response is not JSON") from exc
    if not isinstance(parsed, dict):
        raise ValueError("response is not a JSON object")
    return parsed
