import json

from underwriting.agents.section import schema_instructions, write_section
from underwriting.models import ModelAdapter
from underwriting.schemas import RiskSection

RISK_SYSTEM = f"""
You score one personal auto application from 0 to 100. 0 is the lowest risk and 100 is the highest.
Use bureau flags, credit_band, and loss_history, together with material form facts: age, years licensed, and prior claims. Do not score from the form alone when enrichment is present.
Raise the score for poor credit, at-fault accidents, violations, recent_at_fault, major_violations, high garaging risk, a driver under 25 or licensed under 3 years, and 3 or more prior claims. Lower it for excellent credit, a loss history of all zeros, and 0 prior claims.
Score bands: 0-30 is a clean file, 31-60 is moderate or uncertain, 61-100 is high risk. When data is missing, stay in 31-60 unless the facts that are present already show high risk.
drivers is a short list of the facts that moved the score, up or down, such as "poor credit", "two at-fault accidents", or "excellent credit". drivers is never empty: a low score lists the facts that kept it low. Every driver must be a fact in intake or enrichment. Say "clean loss history" only when loss_history is present and all zeros. When a fact is unknown or null, name it as missing, for example "credit unknown" or "no loss history on file".
missing_data is true when flags include incomplete_bureau, credit_band is unknown, loss_history is null, or intake.missing_fields is not empty. Otherwise missing_data is false.
{schema_instructions(RiskSection)}
""".strip()


def risk_scoring_agent(case: dict, model: ModelAdapter) -> dict:
    if case["case_id"] == "app-timeout":
        raise TimeoutError("simulated risk-scoring timeout")
    user = "\n".join(
        [
            "Use bureau flags, credit, and loss history, not only the form.",
            json.dumps(
                {"intake": case["intake"], "enrichment": case["enrichment"]}
            ),
        ]
    )
    result = model.complete(RISK_SYSTEM, user)
    return write_section(case, result, RiskSection, "risk")
