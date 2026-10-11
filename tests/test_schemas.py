import pytest
from pydantic import ValidationError
from underwriting.schemas import IntakeSection, RecommendationSection, RiskSection


def test_score_string_coerces_to_int():
    parsed = RiskSection.model_validate(
        {"score": "82", "drivers": ["credit"], "missing_data": False}
    )

    assert parsed.score == 82


def test_decision_approved_is_rejected():
    with pytest.raises(ValidationError):
        RecommendationSection.model_validate(
            {"decision": "approved", "reason": "looks fine"}
        )


def test_missing_decision_is_rejected():
    with pytest.raises(ValidationError):
        RecommendationSection.model_validate({"reason": "no decision given"})


def test_score_above_100_is_rejected():
    with pytest.raises(ValidationError):
        RiskSection.model_validate(
            {"score": 101, "drivers": [], "missing_data": False}
        )


def test_stray_keys_are_dropped():
    parsed = IntakeSection.model_validate(
        {
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
    )

    assert "notes" not in parsed.model_dump()
