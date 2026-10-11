import json
from datetime import datetime, timedelta

from underwriting.models import ModelResult, ScriptedModelAdapter
from underwriting.orchestrator import run_case
from underwriting.pricing import cost_usd
from underwriting.tracing import Tracer

RAW = {
    "case_id": "app-clean",
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
    "loss_history": {
        "at_fault_accidents": 0,
        "violations": 0,
        "total_losses": 0,
    },
    "vehicle_symbol": 12,
    "garaging_risk": "low",
    "flags": [],
    "source": "mock_bureau",
}


def _result(content, input_tokens, output_tokens):
    return ModelResult(
        content=content,
        model="scripted",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
    )


def test_run_case_hands_intake_to_enrichment_and_traces_both_spans(tmp_path):
    adapter = ScriptedModelAdapter(
        [
            _result(INTAKE, input_tokens=10, output_tokens=4),
            _result(ENRICHMENT, input_tokens=12, output_tokens=6),
        ]
    )
    tracer = Tracer(tmp_path)

    case = run_case(RAW, adapter, tracer)

    assert case["intake"]["applicant_name"] == "Ada Lovelace"
    assert case["intake"]["missing_fields"] == []
    assert case["enrichment"]["source"] == "mock_bureau"
    assert case["enrichment"]["credit_band"] == "excellent"
    assert case["risk"] is None
    assert case["recommendation"] is None
    assert case["status"] == "in_progress"
    assert "_last_usage" not in case

    enrichment_prompt = adapter.prompts[1][1]
    assert "Ada Lovelace" in enrichment_prompt
    assert "D1002001" in enrichment_prompt
    assert "missing_fields" in enrichment_prompt
    assert "missing_fields" not in adapter.prompts[0][1]

    spans = json.loads((tmp_path / "app-clean.json").read_text())
    assert [span["agent"] for span in spans] == [
        "intake_agent",
        "mock_bureau",
        "enrichment_agent",
    ]

    intake_span, bureau_span, enrichment_span = spans
    assert intake_span["input_source"] == [
        {"field": "raw_application", "from": "user"}
    ]
    assert intake_span["output"]["license_number"] == "D1002001"
    assert intake_span["usage"] == {"input_tokens": 10, "output_tokens": 4}
    assert intake_span["cost_usd"] == cost_usd(10, 4)
    assert intake_span["model"] == "scripted"
    assert intake_span["decision"] is None
    assert intake_span["status"] == "ok"
    _assert_timing(intake_span)

    assert bureau_span["input_source"] == [
        {"field": "intake", "from": "intake_agent"}
    ]
    assert bureau_span["output"]["report_id"] == "R-1001"
    assert bureau_span["output"]["credit_score"] == 790
    assert bureau_span["model"] is None
    assert bureau_span["usage"] is None
    assert bureau_span["cost_usd"] is None
    assert bureau_span["decision"] is None
    assert bureau_span["status"] == "ok"
    _assert_timing(bureau_span)

    assert enrichment_span["input_source"] == [
        {"field": "intake", "from": "intake_agent"},
        {"field": "bureau_report", "from": "mock_bureau"},
    ]
    assert enrichment_span["input"]["intake"]["applicant_name"] == "Ada Lovelace"
    assert enrichment_span["input"]["bureau_report"]["credit_score"] == 790
    assert enrichment_span["output"]["credit_band"] == "excellent"
    assert enrichment_span["usage"] == {"input_tokens": 12, "output_tokens": 6}
    assert enrichment_span["cost_usd"] == cost_usd(12, 6)
    assert enrichment_span["model"] == "scripted"
    assert enrichment_span["decision"] is None
    assert enrichment_span["status"] == "ok"
    _assert_timing(enrichment_span)


def _assert_timing(span):
    assert isinstance(span["duration_ms"], int)
    assert span["duration_ms"] >= 0
    started = datetime.fromisoformat(span["started_at"])
    assert started.utcoffset() == timedelta(0)
