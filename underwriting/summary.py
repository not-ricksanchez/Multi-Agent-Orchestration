import json
from pathlib import Path


def summarize_trace(path: str | Path) -> dict:
    spans = json.loads(Path(path).read_text())
    duration_ms = 0
    cost_usd = 0.0
    input_tokens = 0
    output_tokens = 0
    for span in spans:
        duration_ms += span["duration_ms"]
        if span.get("cost_usd") is not None:
            cost_usd += span["cost_usd"]
        usage = span.get("usage") or {}
        input_tokens += usage.get("input_tokens") or 0
        output_tokens += usage.get("output_tokens") or 0
    return {
        "duration_ms": duration_ms,
        "cost_usd": cost_usd,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }
