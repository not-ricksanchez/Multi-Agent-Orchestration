import json

from underwriting.agents.section import schema_instructions, write_section
from underwriting.models import ModelAdapter
from underwriting.schemas import RecommendationSection

RECOMMENDATION_SYSTEM = f"""
You decide one personal auto application. Use intake, enrichment, and risk together. decision must be exactly approve, deny, or refer.
Apply these rules in order and stop at the first one that matches:
1. deny when credit_band is poor, or flags include recent_at_fault or major_violations, or prior_claims is 3 or more.
2. refer when missing_data is true, credit_band is unknown, loss_history is null, flags include incomplete_bureau, or intake.missing_fields is not empty.
3. approve when credit_band is excellent or fair, loss_history is present with at_fault_accidents 0 and violations 1 or fewer, and risk score is 60 or lower.
4. Otherwise refer, because the file is too uncertain to approve or deny.
A loss_history of all zeros is present and clean. It is not null and is not a reason to refer.
reason is one or two sentences. Start it with the decision and the condition that matched, for example "Refer: missing data." Then cite the credit band, loss history, flags, risk score, and every name in intake.missing_fields. Do not invent facts that are not in those sections.
{schema_instructions(RecommendationSection)}
""".strip()


def recommendation_agent(case: dict, model: ModelAdapter) -> dict:
    if case.get("risk") is None:
        raise ValueError("risk section is missing")
    user = json.dumps(
        {
            "intake": case["intake"],
            "enrichment": case["enrichment"],
            "risk": case["risk"],
        }
    )
    result = model.complete(RECOMMENDATION_SYSTEM, user)
    return write_section(case, result, RecommendationSection, "recommendation")
