import json
import os
from dataclasses import dataclass
from typing import Protocol
from urllib.error import URLError
from urllib.request import Request, urlopen

from underwriting.errors import ModelResponseError
from underwriting.schemas import IntakeSection


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
    def __init__(
        self,
        base_url: str | None = None,
        model: str = "qwen3:8b",
        timeout: float = 120,
        thinking: bool = False,
        response_schema: dict | None = None,
    ):
        if base_url is None:
            base_url = os.environ.get("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.thinking = thinking
        self.response_schema = response_schema

    def complete(self, system: str, user: str) -> ModelResult:
        payload = {
            "model": self.model,
            "stream": False,
            "format": "json",
            "think": self.thinking,
            "options": {"temperature": 0},
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        if self.response_schema is not None:
            payload["format"] = self.response_schema
        request = Request(
            f"{self.base_url}/api/chat",
            data=json.dumps(payload).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout) as response:
                body = _json_object(response.read().decode())
        except URLError as exc:
            if isinstance(exc.reason, TimeoutError):
                raise TimeoutError(
                    f"Ollama call timed out after {self.timeout}s"
                ) from exc
            raise ConnectionError(f"Ollama is unreachable: {exc.reason}") from exc
        content = _json_object(body["message"]["content"])
        return ModelResult(
            content=content,
            model=self.model,
            input_tokens=body["prompt_eval_count"],
            output_tokens=body["eval_count"],
        )


class OllamaIntakeAdapter(OllamaModelAdapter):
    def __init__(self, base_url: str | None = None, timeout: float = 120):
        super().__init__(
            base_url=base_url,
            model="qwen3:4b",
            timeout=timeout,
            response_schema=IntakeSection.model_json_schema(),
        )


def _json_object(text: str) -> dict:
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ModelResponseError("response is not JSON") from exc
    if not isinstance(parsed, dict):
        raise ModelResponseError("response is not a JSON object")
    return parsed
