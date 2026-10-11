import pytest
from pydantic import ValidationError

from underwriting.agents import intake_agent
from underwriting.models import ModelResult, ScriptedModelAdapter
from underwriting.schemas import IntakeSection

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
    "notes": "drop me",
}


def _case():
    return {
        "case_id": "app-clean",
        "raw_application": {
            "case_id": "app-clean",
            "applicant_name": "Ada Lovelace",
            "license_number": "D1002001",
            "age": 40,
            "years_licensed": 20,
            "vehicle_year": 2018,
            "vehicle_make": "Honda",
            "coverage_amount": 500000,
            "prior_claims": 0,
        },
        "intake": None,
        "enrichment": {"marker": "ENRICHMENT_KEEP"},
        "risk": {"marker": "RISK_KEEP"},
        "recommendation": {"marker": "RECOMMENDATION_KEEP"},
        "status": "in_progress",
        "failure": None,
    }


def _result(content):
    return ModelResult(
        content=content, model="scripted", input_tokens=11, output_tokens=7
    )


def test_intake_writes_validated_section_and_leaves_others():
    case = _case()
    adapter = ScriptedModelAdapter([_result(INTAKE)])

    intake_agent(case, adapter)

    assert case["intake"] == IntakeSection.model_validate(INTAKE).model_dump()
    assert "notes" not in case["intake"]
    assert case["enrichment"] == {"marker": "ENRICHMENT_KEEP"}
    assert case["risk"] == {"marker": "RISK_KEEP"}
    assert case["recommendation"] == {"marker": "RECOMMENDATION_KEEP"}
    assert case["_last_usage"] == {
        "model": "scripted",
        "input_tokens": 11,
        "output_tokens": 7,
    }
    system, user = adapter.prompts[0]
    assert "Ada Lovelace" in user
    assert "D1002001" in user
    assert "ENRICHMENT_KEEP" not in user
    assert "applicant_name" in system
    assert "missing_fields" in system
    assert "IntakeSection" in system
    assert '"type": "integer"' in system
    assert "Do not invent" in system
    assert "This schema is the required response" in system
    assert "missing_fields" in system


def test_intake_invalid_reply_leaves_section_empty():
    case = _case()
    adapter = ScriptedModelAdapter([_result({"license_number": "D1002001"})])

    with pytest.raises(ValidationError):
        intake_agent(case, adapter)

    assert case["intake"] is None
    assert case["enrichment"] == {"marker": "ENRICHMENT_KEEP"}
