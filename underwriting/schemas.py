from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class _Section(BaseModel):
    model_config = ConfigDict(extra="ignore")


class IntakeSection(_Section):
    applicant_name: str
    license_number: str
    age: int
    years_licensed: int | None
    vehicle_year: int
    vehicle_make: str
    coverage_amount: int
    prior_claims: int | None
    missing_fields: list[str]


class LossHistory(_Section):
    at_fault_accidents: int
    violations: int
    total_losses: int


class EnrichmentSection(_Section):
    credit_band: Literal["excellent", "fair", "poor", "unknown"]
    loss_history: LossHistory | None
    vehicle_symbol: int | None
    garaging_risk: Literal["low", "high", "unknown"]
    flags: list[str]
    source: Literal["mock_bureau"]


class RiskSection(_Section):
    score: int = Field(ge=0, le=100)
    drivers: list[str]
    missing_data: bool


class RecommendationSection(_Section):
    decision: Literal["approve", "deny", "refer"]
    reason: str
