import pytest
from pydantic import ValidationError

from underwriting.agents import risk_scoring_agent
from underwriting.models import ModelResult, ScriptedModelAdapter
from underwriting.schemas import RiskSection

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


def _case():
    return {
        "case_id": "APP-1001",
        "raw_application": {"secret_marker": "RAW_ONLY"},
        "intake": dict(INTAKE),
        "enrichment": dict(ENRICHMENT),
        "risk": None,
        "recommendation": {"marker": "RECOMMENDATION_KEEP"},
        "status": "in_progress",
        "failure": None,
    }


def _result(content):
    return ModelResult(
        content=content, model="scripted", input_tokens=15, output_tokens=5
    )


def test_risk_writes_validated_section_from_intake_and_enrichment():
    case = _case()
    adapter = ScriptedModelAdapter([_result(RISK)])

    risk_scoring_agent(case, adapter)

    assert case["risk"] == RiskSection.model_validate(RISK).model_dump()
    assert case["intake"] == INTAKE
    assert case["enrichment"] == ENRICHMENT
    assert case["recommendation"] == {"marker": "RECOMMENDATION_KEEP"}
    system, user = adapter.prompts[0]
    assert "Ada Lovelace" in user
    assert "excellent" in user
    assert "loss history" in user
    assert "not only the form" in user
    assert "RAW_ONLY" not in user
    assert "RECOMMENDATION_KEEP" not in user
    assert "score" in system
    assert "missing_data" in system
    assert "RiskSection" in system
    assert '"maximum": 100' in system
    assert "lowest risk" in system
    assert "This schema is the required response" in system
    assert "missing_data is true" in system


def test_risk_invalid_score_leaves_section_empty():
    case = _case()
    adapter = ScriptedModelAdapter(
        [_result({"score": "nope", "drivers": [], "missing_data": False})]
    )

    with pytest.raises(ValidationError):
        risk_scoring_agent(case, adapter)

    assert case["risk"] is None
    assert case["enrichment"] == ENRICHMENT


def test_risk_timeout_does_not_call_the_adapter():
    case = _case()
    case["case_id"] = "app-timeout"
    adapter = ScriptedModelAdapter([_result(RISK)])

    with pytest.raises(TimeoutError, match="simulated risk-scoring timeout"):
        risk_scoring_agent(case, adapter)

    assert case["risk"] is None
    assert adapter.prompts == []
    assert case["recommendation"] == {"marker": "RECOMMENDATION_KEEP"}
