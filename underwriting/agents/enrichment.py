import json

from underwriting.agents.section import schema_instructions, write_section
from underwriting.models import ModelAdapter
from underwriting.schemas import EnrichmentSection

ENRICHMENT_SYSTEM = f"""
You map a vendor motor-vehicle report into the enrichment section for one personal auto policy.
Take credit, losses, vehicle symbol, territory, and flags from the bureau report only. Do not restate intake fields such as name, age, license number, or vehicle.
Do not invent a credit score, event, ISO symbol, or territory when the report has null. report_id NOT_FOUND means the bureau has no report: treat credit, events, symbol, and territory as unknown.
An empty list [] and null are different. mvr_events [] means the bureau checked and found no events, so loss_history is all zeros. mvr_events null means the bureau has no event data, so loss_history is null.
flags may contain only recent_at_fault, major_violations, and incomplete_bureau. source is always mock_bureau.
Apply every mapping rule in the user message mechanically. Check each flag rule separately before writing flags.
{schema_instructions(EnrichmentSection)}
""".strip()

ENRICHMENT_RULES = """
Mapping rules:
- credit_band: credit_score 750 or above is excellent, 650-749 is fair, 1-649 is poor, null is unknown.
- loss_history: at_fault_accidents counts events whose type is at_fault_accident. violations counts events whose type is major_violation or minor_violation. total_losses is the number of events.
  - mvr_events [] gives {"at_fault_accidents": 0, "violations": 0, "total_losses": 0}. It is not null.
  - mvr_events null gives loss_history null.
- vehicle_symbol: copy iso_symbol unchanged. Null iso_symbol gives vehicle_symbol null.
- garaging_risk: garaging_territory suburban or rural is low, urban is high, null is unknown.
- flags, check each rule and include every one that applies:
  - recent_at_fault if mvr_events contains at least one at_fault_accident.
  - major_violations if mvr_events contains at least one major_violation.
  - incomplete_bureau only if credit_score is null, or mvr_events is null, or report_id is NOT_FOUND. A numeric credit_score and an mvr_events list, even an empty one, are complete: do not add incomplete_bureau, however bad the record is.
  - If none apply, flags is [].
- source is mock_bureau.
Examples:
- credit_score 760, mvr_events [], iso_symbol 10, territory rural gives credit_band excellent, loss_history all zeros, vehicle_symbol 10, garaging_risk low, flags [].
- credit_score 680, mvr_events one at_fault_accident and one minor_violation, iso_symbol 20, territory urban gives credit_band fair, loss_history {"at_fault_accidents": 1, "violations": 1, "total_losses": 2}, vehicle_symbol 20, garaging_risk high, flags ["recent_at_fault"].
- report_id NOT_FOUND with every field null gives credit_band unknown, loss_history null, vehicle_symbol null, garaging_risk unknown, flags ["incomplete_bureau"].
""".strip()


def enrichment_agent(case: dict, model: ModelAdapter, report: dict) -> dict:
    user = "\n".join(
        [
            ENRICHMENT_RULES,
            json.dumps({"intake": case["intake"], "bureau_report": report}),
        ]
    )
    result = model.complete(ENRICHMENT_SYSTEM, user)
    return write_section(case, result, EnrichmentSection, "enrichment")
