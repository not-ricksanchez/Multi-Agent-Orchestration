import json

from underwriting.agents.section import schema_instructions, write_section
from underwriting.models import ModelAdapter
from underwriting.schemas import RiskSection

RISK_SYSTEM = f"""
You score one personal auto application from 0 to 100. 0 is the lowest risk and 100 is the highest.
Use bureau flags, credit_band, and loss_history, together with material form facts: age, years licensed, and prior claims. Do not score from the form alone when enrichment is present.
Raise the score for poor credit, at-fault accidents, violations, recent_at_fault, major_violations, high garaging risk, and several prior claims. Lower it for excellent credit and a clean loss history.
drivers is a short list of the facts that moved the score, such as "poor credit" or "two at-fault accidents".
missing_data is true when flags include incomplete_bureau, credit_band is unknown, loss_history is null, or intake.missing_fields names a fact the score depends on. Otherwise missing_data is false.
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
