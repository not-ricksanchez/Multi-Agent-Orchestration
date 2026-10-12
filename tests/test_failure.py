import json

import pytest
from underwriting.errors import ModelResponseError
from underwriting.models import ModelResult, ScriptedModelAdapter
from underwriting.orchestrator import run_case
from underwriting.pricing import cost_usd
from underwriting.tracing import Tracer

RAW = {
    "case_id": "app-timeout",
    "applicant_name": "Ada Lovelace",
    "license_number": "D1002001",
    "age": 40,
    "years_licensed": 20,
    "vehicle_year": 2018,
    "vehicle_make": "Honda",
    "coverage_amount": 500000,
    "prior_claims": 0,
}

INTAKE = {
    "applicant_name": "Ada Lovelace",
    "license_number": "D1002001",
    "age": 40,
    "years_licensed": 20,
    "vehicle_year": 2018,
    "vehicle_make": "Honda",
    "coverage_amount": 500000,
    "prior_claims": 0,
    "missing_fields": [],
}

ENRICHMENT = {
    "credit_band": "excellent",
    "loss_history": {"at_fault_accidents": 0, "violations": 0, "total_losses": 0},
    "vehicle_symbol": 12,
    "garaging_risk": "low",
    "flags": [],
    "source": "mock_bureau",
}

RISK = {"score": 15, "drivers": ["excellent credit"], "missing_data": False}

INVALID_RISK = {"score": "nope", "drivers": [], "missing_data": False}

RECOMMENDATION = {"decision": "approve", "reason": "Approve: clean file."}


def _result(content, input_tokens=10, output_tokens=5):
    return ModelResult(
        content=content,
        model="scripted",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


class RaisingAdapter(ScriptedModelAdapter):
    def complete(self, system, user):
        result = super().complete(system, user)
        if isinstance(result, Exception):
            raise result
        return result


def _run(tmp_path, raw, results, **kwargs):
    adapter = RaisingAdapter(results)
    tracer = Tracer(tmp_path)
    sleeps = []
    case = run_case(
        raw, adapter, tracer, max_attempts=3, sleep=sleeps.append, **kwargs
    )
    spans = json.loads(tracer.path_for(raw["case_id"]).read_text())
    return case, spans, sleeps, adapter


def test_timeout_retries_then_escalates_without_a_recommendation(tmp_path):
    case, spans, sleeps, adapter = _run(
        tmp_path, RAW, [_result(INTAKE), _result(ENRICHMENT)]
    )

    assert case["status"] == "escalated"
    assert case["failure"] == {
        "agent": "risk_scoring_agent",
        "error": "TimeoutError",
        "attempts": 3,
    }
    assert case["intake"] is not None
    assert case["enrichment"] is not None
    assert case["risk"] is None
    assert case["recommendation"] is None
    assert "_last_usage" not in case
    assert len(adapter.prompts) == 2
    assert sleeps == [0.5, 1.0]

    assert [span["agent"] for span in spans] == [
        "intake_agent",
        "mock_bureau",
        "enrichment_agent",
        "risk_scoring_agent",
        "risk_scoring_agent",
        "risk_scoring_agent",
        "orchestrator",
    ]
    risk_spans = spans[3:6]
    assert [span["attempt"] for span in risk_spans] == [1, 2, 3]
    assert [span["status"] for span in risk_spans] == ["retry", "retry", "escalated"]
    for span in risk_spans:
        assert span["max_attempts"] == 3
        assert span["output"] is None
        assert span["error"] == {
            "type": "TimeoutError",
            "message": "simulated risk-scoring timeout",
        }
        assert span["usage"] is None
        assert span["cost_usd"] is None
        assert span["input"]["enrichment"]["credit_band"] == "excellent"
        assert span["duration_ms"] >= 0

    escalation = spans[6]
    assert escalation["step"] == "escalation"
    assert escalation["decision"] == "escalate"
    assert escalation["status"] == "escalated"
    assert escalation["input_source"] == [{"field": "risk", "from": "risk_scoring_agent"}]
    assert escalation["output"] == {"status": "escalated", "failure": case["failure"]}
    assert escalation["error"]["type"] == "TimeoutError"
    assert escalation["usage"] is None
    assert escalation["cost_usd"] is None


def test_invalid_reply_retries_then_escalates_and_keeps_token_cost(tmp_path):
    raw = dict(RAW, case_id="APP-1001")

    case, spans, sleeps, _ = _run(
        tmp_path,
        raw,
        [
            _result(INTAKE),
            _result(ENRICHMENT),
            _result(INVALID_RISK, 15, 5),
            _result(INVALID_RISK, 15, 5),
            _result(INVALID_RISK, 15, 5),
        ],
    )

    assert case["status"] == "escalated"
    assert case["failure"] == {
        "agent": "risk_scoring_agent",
        "error": "ValidationError",
        "attempts": 3,
    }
    assert case["risk"] is None
    assert case["recommendation"] is None
    assert "_last_usage" not in case
    assert sleeps == [0.5, 1.0]

    risk_spans = [span for span in spans if span["agent"] == "risk_scoring_agent"]
    assert [span["status"] for span in risk_spans] == ["retry", "retry", "escalated"]
    for span in risk_spans:
        assert span["error"]["type"] == "ValidationError"
        assert "score" in span["error"]["message"]
        assert span["output"] is None
        assert span["usage"] == {"input_tokens": 15, "output_tokens": 5}
        assert span["cost_usd"] == cost_usd(15, 5)
        assert span["model"] == "scripted"
    assert spans[-1]["agent"] == "orchestrator"
    assert spans[-1]["decision"] == "escalate"


def test_invalid_reply_then_valid_reply_recovers(tmp_path):
    raw = dict(RAW, case_id="APP-1001")

    case, spans, sleeps, _ = _run(
        tmp_path,
        raw,
        [
            _result(INTAKE),
            _result(ENRICHMENT),
            _result(INVALID_RISK),
            _result(RISK),
            _result(RECOMMENDATION),
        ],
    )

    assert case["status"] == "complete"
    assert case["failure"] is None
    assert case["risk"] == RISK
    assert case["recommendation"]["decision"] == "approve"
    assert sleeps == [0.5]

    risk_spans = [span for span in spans if span["agent"] == "risk_scoring_agent"]
    assert [(span["attempt"], span["status"]) for span in risk_spans] == [
        (1, "retry"),
        (2, "ok"),
    ]
    assert risk_spans[1]["error"] is None
    assert risk_spans[1]["output"] == RISK
    assert "orchestrator" not in {span["agent"] for span in spans}
    assert spans[-1]["agent"] == "recommendation_agent"
    assert spans[-1]["attempt"] == 1


@pytest.mark.parametrize(
    "error",
    [
        ModelResponseError("response is not JSON"),
        ConnectionError("Ollama is unreachable: [Errno 111] Connection refused"),
    ],
)
def test_adapter_errors_retry_then_escalate_instead_of_crashing(tmp_path, error):
    raw = dict(RAW, case_id="APP-1001")

    case, spans, sleeps, adapter = _run(
        tmp_path, raw, [_result(INTAKE), error, error, error]
    )

    assert case["status"] == "escalated"
    assert case["failure"] == {
        "agent": "enrichment_agent",
        "error": type(error).__name__,
        "attempts": 3,
    }
    assert case["intake"] is not None
    assert case["enrichment"] is None
    assert case["risk"] is None
    assert case["recommendation"] is None
    assert len(adapter.prompts) == 4
    assert sleeps == [0.5, 1.0]

    enrichment_spans = [span for span in spans if span["agent"] == "enrichment_agent"]
    assert [span["status"] for span in enrichment_spans] == [
        "retry",
        "retry",
        "escalated",
    ]
    for span in enrichment_spans:
        assert span["error"] == {"type": type(error).__name__, "message": str(error)}
        assert span["output"] is None
        assert span["usage"] is None
        assert span["cost_usd"] is None
    assert spans[-1]["agent"] == "orchestrator"
    assert spans[-1]["input_source"] == [
        {"field": "enrichment", "from": "enrichment_agent"}
    ]


def test_connection_error_then_success_recovers(tmp_path):
    raw = dict(RAW, case_id="APP-1001")

    case, spans, sleeps, _ = _run(
        tmp_path,
        raw,
        [
            ConnectionError("Ollama is unreachable: [Errno 111] Connection refused"),
            _result(INTAKE),
            _result(ENRICHMENT),
            _result(RISK),
            _result(RECOMMENDATION),
        ],
    )

    assert case["status"] == "complete"
    assert case["recommendation"]["decision"] == "approve"
    assert sleeps == [0.5]
    intake_spans = [span for span in spans if span["agent"] == "intake_agent"]
    assert [(span["attempt"], span["status"]) for span in intake_spans] == [
        (1, "retry"),
        (2, "ok"),
    ]
    assert intake_spans[0]["error"]["type"] == "ConnectionError"


@pytest.mark.parametrize("contents", [None, "[{not json", '{"license_number": "D1002001"}'])
def test_bureau_failure_escalates_immediately_without_enrichment(tmp_path, contents):
    bureau = tmp_path / "bureau.json"
    if contents is not None:
        bureau.write_text(contents)
    raw = dict(RAW, case_id="APP-1001")

    case, spans, sleeps, adapter = _run(
        tmp_path / "traces", raw, [_result(INTAKE)], bureau_path=bureau
    )

    assert case["status"] == "escalated"
    assert case["failure"] == {
        "agent": "mock_bureau",
        "error": "BureauError",
        "attempts": 1,
    }
    assert case["intake"] is not None
    assert case["enrichment"] is None
    assert case["risk"] is None
    assert case["recommendation"] is None
    assert len(adapter.prompts) == 1
    assert sleeps == []

    assert [span["agent"] for span in spans] == [
        "intake_agent",
        "mock_bureau",
        "orchestrator",
    ]
    bureau_span, escalation = spans[1], spans[2]
    assert bureau_span["status"] == "escalated"
    assert bureau_span["output"] is None
    assert bureau_span["attempt"] == 1
    assert bureau_span["max_attempts"] == 1
    assert bureau_span["error"]["type"] == "BureauError"
    assert escalation["decision"] == "escalate"
    assert escalation["input_source"] == [
        {"field": "bureau_report", "from": "mock_bureau"}
    ]


def test_failed_attempts_still_record_the_model_name(tmp_path):
    class NamedAdapter(RaisingAdapter):
        model = "qwen3:8b"

    adapter = NamedAdapter([_result(INTAKE), _result(ENRICHMENT)])
    tracer = Tracer(tmp_path)

    run_case(RAW, adapter, tracer, max_attempts=3, sleep=lambda _: None)

    spans = json.loads(tracer.path_for(RAW["case_id"]).read_text())
    risk_spans = [span for span in spans if span["step"] == "risk"]
    assert [span["status"] for span in risk_spans] == ["retry", "retry", "escalated"]
    assert {span["model"] for span in risk_spans} == {"qwen3:8b"}
    assert all(span["usage"] is None and span["cost_usd"] is None for span in risk_spans)
    by_step = {span["step"]: span for span in spans}
    assert by_step["mock_bureau"]["model"] is None
    assert by_step["escalation"]["model"] is None
