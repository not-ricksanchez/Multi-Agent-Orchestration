import pytest
from pydantic import ValidationError
from underwriting.agents import recommendation_agent
from underwriting.models import ModelResult, ScriptedModelAdapter
from underwriting.schemas import RecommendationSection

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

RECOMMENDATION = {"decision": "approve", "reason": "clean record"}


def _case():
    return {
        "case_id": "APP-1001",
        "raw_application": {"secret_marker": "RAW_ONLY"},
        "intake": dict(INTAKE),
        "enrichment": dict(ENRICHMENT),
        "risk": dict(RISK),
        "recommendation": None,
        "status": "in_progress",
        "failure": None,
    }


def _result(content):
    return ModelResult(
        content=content, model="scripted", input_tokens=8, output_tokens=4
    )


def test_recommendation_writes_validated_decision():
    case = _case()
    adapter = ScriptedModelAdapter([_result(RECOMMENDATION)])

    recommendation_agent(case, adapter)

    assert case["recommendation"] == RecommendationSection.model_validate(
        RECOMMENDATION
    ).model_dump()
    assert case["intake"] == INTAKE
    assert case["enrichment"] == ENRICHMENT
    assert case["risk"] == RISK
    system, user = adapter.prompts[0]
    assert "Ada Lovelace" in user
    assert "excellent" in user
    assert "18" in user
    assert "RAW_ONLY" not in user
    assert "decision" in system
    assert "reason" in system
    assert "RecommendationSection" in system
    assert '"enum"' in system
    assert "approve when" in system
    assert "This schema is the required response" in system
    assert "deny when" in system
    assert "refer when" in system


def test_recommendation_invalid_decision_leaves_section_empty():
    case = _case()
    adapter = ScriptedModelAdapter(
        [_result({"decision": "approved", "reason": "looks fine"})]
    )

    with pytest.raises(ValidationError):
        recommendation_agent(case, adapter)

    assert case["recommendation"] is None
    assert case["risk"] == RISK


def test_recommendation_missing_risk_does_not_call_the_adapter():
    case = _case()
    case["risk"] = None
    adapter = ScriptedModelAdapter([_result(RECOMMENDATION)])

    with pytest.raises(ValueError):
        recommendation_agent(case, adapter)

    assert case["recommendation"] is None
    assert adapter.prompts == []
