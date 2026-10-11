import json

from underwriting.agents.section import schema_instructions, write_section
from underwriting.models import ModelAdapter
from underwriting.schemas import IntakeSection

INTAKE_SYSTEM = f"""
You normalize one personal auto application into the intake section. There is no home product.
Copy values from the application exactly. Do not invent a name, license number, age, vehicle, coverage amount, or claim count. Write numbers as integers, so "40" becomes 40.
If years_licensed or prior_claims is absent, blank, or null, set that field to null and add its name to missing_fields. A value of 0 is present, not missing: prior_claims 0 stays 0 and is not listed.
missing_fields lists only inputs that were absent or blank. Use [] when the form is complete.
Example: an application with no prior_claims key becomes prior_claims null and missing_fields ["prior_claims"].
Example: an application with prior_claims 0 keeps prior_claims 0 and missing_fields [].
{schema_instructions(IntakeSection)}
""".strip()


def intake_agent(case: dict, model: ModelAdapter) -> dict:
    user = json.dumps({"raw_application": case["raw_application"]})
    result = model.complete(INTAKE_SYSTEM, user)
    return write_section(case, result, IntakeSection, "intake")
