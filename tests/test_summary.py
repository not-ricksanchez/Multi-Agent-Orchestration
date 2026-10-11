import json

from underwriting.summary import summarize_trace


def test_summarize_trace_sums_duration_and_cost(tmp_path):
    path = tmp_path / "APP-1001.json"
    path.write_text(
        json.dumps(
            [
                {
                    "duration_ms": 100,
                    "cost_usd": 0.5,
                    "usage": {"input_tokens": 10, "output_tokens": 4},
                },
                {
                    "duration_ms": 5,
                    "cost_usd": None,
                    "usage": None,
                },
                {
                    "duration_ms": 40,
                    "cost_usd": 0.25,
                    "usage": {"input_tokens": 12, "output_tokens": 6},
                },
            ]
        )
    )

    summary = summarize_trace(path)

    assert summary["duration_ms"] == 145
    assert summary["cost_usd"] == 0.75
    assert summary["input_tokens"] == 22
    assert summary["output_tokens"] == 10
