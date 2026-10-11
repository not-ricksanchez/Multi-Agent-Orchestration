import pytest
from pydantic import ValidationError

from underwriting.agents import enrichment_agent
from underwriting.models import ModelResult, ScriptedModelAdapter
from underwriting.schemas import EnrichmentSection

REPORT = {
    "report_id": "R-1001",
    "pulled_at": "2026-10-01",
    "license_number": "D1002001",
    "credit_score": 790,
    "mvr_events": [],
    "iso_symbol": 12,
    "garaging_territory": "suburban",
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
    "applicant_name": "Ada Lovelace",
}


def _case():
    return {
        "case_id": "APP-1001",
        "raw_application": {
            "case_id": "APP-1001",
            "applicant_name": "Ada Lovelace",
            "license_number": "D1002001",
            "secret_marker": "RAW_ONLY",
        },
        "intake": dict(INTAKE),
        "enrichment": None,
        "risk": {"marker": "RISK_KEEP"},
        "recommendation": {"marker": "RECOMMENDATION_KEEP"},
        "status": "in_progress",
        "failure": None,
    }


def _result(content):
    return ModelResult(
        content=content, model="scripted", input_tokens=20, output_tokens=9
    )


def test_enrichment_writes_validated_section_from_bureau_report():
    case = _case()
    adapter = ScriptedModelAdapter([_result(ENRICHMENT)])

    enrichment_agent(case, adapter, REPORT)

    assert case["enrichment"] == EnrichmentSection.model_validate(ENRICHMENT).model_dump()
    assert "applicant_name" not in case["enrichment"]
    assert case["intake"] == INTAKE
    assert case["risk"] == {"marker": "RISK_KEEP"}
    assert case["recommendation"] == {"marker": "RECOMMENDATION_KEEP"}
    system, user = adapter.prompts[0]
    assert "Ada Lovelace" in user
    assert "D1002001" in user
    assert "790" in user
    assert "R-1001" in user
    assert "750" in user
    assert "excellent" in user
    assert "at_fault_accidents" in user
    assert "vehicle_symbol" in user
    assert "recent_at_fault" in user
    assert "major_violations" in user
    assert "incomplete_bureau" in user
    assert "mock_bureau" in user
    assert "RAW_ONLY" not in user
    assert "RISK_KEEP" not in user
    assert "credit_band" in system
    assert "garaging_risk" in system
    assert "EnrichmentSection" in system
    assert "LossHistory" in system
    assert "Do not invent" in system
    assert "This schema is the required response" in system
    assert "NOT_FOUND" in system


def test_enrichment_invalid_band_leaves_section_empty():
    case = _case()
    invalid = dict(ENRICHMENT)
    invalid["credit_band"] = "great"
    adapter = ScriptedModelAdapter([_result(invalid)])

    with pytest.raises(ValidationError):
        enrichment_agent(case, adapter, REPORT)

    assert case["enrichment"] is None
    assert case["intake"] == INTAKE
    assert case["risk"] == {"marker": "RISK_KEEP"}
