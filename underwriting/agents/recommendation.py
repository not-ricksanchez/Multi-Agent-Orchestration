import json

from underwriting.agents.section import schema_instructions, write_section
from underwriting.models import ModelAdapter
from underwriting.schemas import RecommendationSection

RECOMMENDATION_SYSTEM = f"""
You decide one personal auto application. Use intake, enrichment, and risk together. decision must be exactly approve, deny, or refer.
approve when credit_band is excellent or fair, loss_history is present and light, flags do not include recent_at_fault or major_violations, and missing_data is false.
deny when credit_band is poor, or flags include recent_at_fault or major_violations, or prior_claims is several.
refer when missing_data is true, credit_band is unknown, loss_history is null, or the file is too thin to approve or deny.
reason is one or two sentences citing the credit band, loss history, flags, risk score, and any missing fields you used. Do not invent facts that are not in those sections.
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
