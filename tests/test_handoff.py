import json
from datetime import datetime, timedelta

from underwriting.models import ModelResult, ScriptedModelAdapter
from underwriting.orchestrator import run_case
from underwriting.pricing import cost_usd
from underwriting.tracing import Tracer

RAW = {
    "case_id": "APP-1001",
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

RISK = {"score": 18, "drivers": ["excellent credit"], "missing_data": False}

RECOMMENDATION = {"decision": "approve", "reason": "excellent credit and a clean record"}


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
            _result(RISK, input_tokens=15, output_tokens=5),
            _result(RECOMMENDATION, input_tokens=8, output_tokens=4),
        ]
    )
    tracer = Tracer(tmp_path)

    case = run_case(RAW, adapter, tracer)

    assert case["intake"]["applicant_name"] == "Ada Lovelace"
    assert case["intake"]["missing_fields"] == []
    assert case["enrichment"]["source"] == "mock_bureau"
    assert case["enrichment"]["credit_band"] == "excellent"
    assert case["risk"] == RISK
    assert case["recommendation"]["decision"] == "approve"
    assert case["status"] == "complete"
    assert "_last_usage" not in case

    enrichment_prompt = adapter.prompts[1][1]
    assert "Ada Lovelace" in enrichment_prompt
    assert "D1002001" in enrichment_prompt
    assert "missing_fields" in enrichment_prompt
    assert "missing_fields" not in adapter.prompts[0][1]

    assert "excellent" in adapter.prompts[2][1]
    assert "18" in adapter.prompts[3][1]

    spans = json.loads(tracer.path_for("APP-1001").read_text())
    assert {span["run_id"] for span in spans} == {tracer.run_id}
    assert [span["agent"] for span in spans] == [
        "intake_agent",
        "mock_bureau",
        "enrichment_agent",
        "risk_scoring_agent",
        "recommendation_agent",
    ]

    intake_span, bureau_span, enrichment_span, risk_span, recommendation_span = spans
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

    assert risk_span["input_source"] == [
        {"field": "intake", "from": "intake_agent"},
        {"field": "enrichment", "from": "enrichment_agent"},
    ]
    assert risk_span["input"]["enrichment"]["credit_band"] == "excellent"
    assert risk_span["output"]["score"] == 18
    assert risk_span["usage"] == {"input_tokens": 15, "output_tokens": 5}
    assert risk_span["cost_usd"] == cost_usd(15, 5)
    assert risk_span["model"] == "scripted"
    assert risk_span["decision"] is None
    assert risk_span["status"] == "ok"
    _assert_timing(risk_span)

    assert recommendation_span["input_source"] == [
        {"field": "intake", "from": "intake_agent"},
        {"field": "enrichment", "from": "enrichment_agent"},
        {"field": "risk", "from": "risk_scoring_agent"},
    ]
    assert recommendation_span["input"]["risk"]["score"] == 18
    assert recommendation_span["output"]["decision"] == "approve"
    assert recommendation_span["decision"] == case["recommendation"]["decision"]
    assert recommendation_span["usage"] == {"input_tokens": 8, "output_tokens": 4}
    assert recommendation_span["cost_usd"] == cost_usd(8, 4)
    assert recommendation_span["model"] == "scripted"
    assert recommendation_span["status"] == "ok"
    _assert_timing(recommendation_span)


def test_scripted_pipeline_decisions(tmp_path):
    cases = [
        ("approve", _clean_case()),
        ("deny", _risky_case()),
        ("refer", _thin_case()),
    ]
    for decision, spec in cases:
        adapter = ScriptedModelAdapter(
            [
                _result(spec["intake"], 1, 1),
                _result(spec["enrichment"], 1, 1),
                _result(spec["risk"], 1, 1),
                _result(
                    {"decision": decision, "reason": spec["reason"]},
                    1,
                    1,
                ),
            ]
        )
        tracer = Tracer(tmp_path)
        case = run_case(spec["raw"], adapter, tracer)
        spans = json.loads(tracer.path_for(spec["raw"]["case_id"]).read_text())

        assert case["recommendation"]["decision"] == decision
        assert case["status"] == "complete"
        assert [span["agent"] for span in spans] == [
            "intake_agent",
            "mock_bureau",
            "enrichment_agent",
            "risk_scoring_agent",
            "recommendation_agent",
        ]
        assert spans[1]["output"]["report_id"] == spec["report_id"]
        assert {item["from"] for item in spans[3]["input_source"]} == {
            "intake_agent",
            "enrichment_agent",
        }
        assert spans[4]["decision"] == decision
        assert spans[4]["cost_usd"] == cost_usd(1, 1)
        _assert_timing(spans[3])
        _assert_timing(spans[4])


def _clean_case():
    return {
        "raw": RAW,
        "intake": INTAKE,
        "enrichment": ENRICHMENT,
        "risk": RISK,
        "reason": "excellent credit and a clean record",
        "report_id": "R-1001",
    }


def _risky_case():
    return {
        "raw": {
            "case_id": "APP-1002",
            "applicant_name": "Jordan Hale",
            "license_number": "D1002002",
            "age": 18,
            "years_licensed": 1,
            "vehicle_year": 2024,
            "vehicle_make": "Coupe",
            "coverage_amount": 100000,
            "prior_claims": 4,
        },
        "intake": {
            "applicant_name": "Jordan Hale",
            "license_number": "D1002002",
            "age": 18,
            "years_licensed": 1,
            "vehicle_year": 2024,
            "vehicle_make": "Coupe",
            "coverage_amount": 100000,
            "prior_claims": 4,
            "missing_fields": [],
        },
        "enrichment": {
            "credit_band": "poor",
            "loss_history": {
                "at_fault_accidents": 2,
                "violations": 3,
                "total_losses": 5,
            },
            "vehicle_symbol": 28,
            "garaging_risk": "high",
            "flags": ["recent_at_fault", "major_violations"],
            "source": "mock_bureau",
        },
        "risk": {
            "score": 91,
            "drivers": ["poor credit", "at-fault accidents"],
            "missing_data": False,
        },
        "reason": "poor credit and major violations",
        "report_id": "R-1002",
    }


def _thin_case():
    return {
        "raw": {
            "case_id": "APP-1003",
            "applicant_name": "Mina Patel",
            "license_number": "D1002003",
            "age": 35,
            "years_licensed": 10,
            "vehicle_year": 2015,
            "vehicle_make": "Toyota",
            "coverage_amount": 250000,
        },
        "intake": {
            "applicant_name": "Mina Patel",
            "license_number": "D1002003",
            "age": 35,
            "years_licensed": 10,
            "vehicle_year": 2015,
            "vehicle_make": "Toyota",
            "coverage_amount": 250000,
            "prior_claims": None,
            "missing_fields": ["prior_claims"],
        },
        "enrichment": {
            "credit_band": "unknown",
            "loss_history": None,
            "vehicle_symbol": None,
            "garaging_risk": "unknown",
            "flags": ["incomplete_bureau"],
            "source": "mock_bureau",
        },
        "risk": {
            "score": 50,
            "drivers": ["incomplete bureau"],
            "missing_data": True,
        },
        "reason": "bureau file is incomplete",
        "report_id": "R-1003",
    }


def _assert_timing(span):
    assert isinstance(span["duration_ms"], int)
    assert span["duration_ms"] >= 0
    started = datetime.fromisoformat(span["started_at"])
    assert started.utcoffset() == timedelta(0)
