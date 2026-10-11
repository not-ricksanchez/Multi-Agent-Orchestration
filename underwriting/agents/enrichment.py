import json
from pathlib import Path

from underwriting.agents.section import schema_instructions, write_section
from underwriting.models import ModelAdapter
from underwriting.schemas import EnrichmentSection
from underwriting.tools import lookup_bureau

DEFAULT_BUREAU_PATH = Path(__file__).resolve().parents[2] / "bureau_reports.json"

ENRICHMENT_SYSTEM = f"""
You map a vendor motor-vehicle report into the enrichment section for one personal auto policy.
Take credit, losses, vehicle symbol, territory, and flags from the bureau report only. Do not restate intake fields such as name, age, license number, or vehicle.
Do not invent a credit score, event, ISO symbol, or territory when the report has null. report_id NOT_FOUND means the bureau has no report: treat credit, events, symbol, and territory as unknown.
flags may contain only recent_at_fault, major_violations, and incomplete_bureau. source is always mock_bureau.
{schema_instructions(EnrichmentSection)}
""".strip()

ENRICHMENT_RULES = """
Mapping rules:
- Credit score 750 or above is excellent, 650-749 is fair, 1-649 is poor, null is unknown.
- at_fault_accidents counts events whose type is at_fault_accident. violations counts major_violation and minor_violation. total_losses is the number of events. An empty event list counts as zeros. Null mvr_events makes loss_history null.
- iso_symbol is copied unchanged to vehicle_symbol. Null iso_symbol makes vehicle_symbol null.
- Territory suburban or rural is garaging low, urban is high, null is unknown.
- Flags: recent_at_fault if any at-fault event, major_violations if any major violation, incomplete_bureau if credit score or events are null. A driver can have more than one flag. If none apply, flags is [].
- source is mock_bureau.
""".strip()


def enrichment_agent(
    case: dict,
    model: ModelAdapter,
    bureau_path: str | Path | None = None,
) -> dict:
    path = DEFAULT_BUREAU_PATH if bureau_path is None else bureau_path
    report = lookup_bureau(case["intake"], path)
    user = "\n".join(
        [
            ENRICHMENT_RULES,
            json.dumps({"intake": case["intake"], "bureau_report": report}),
        ]
    )
    result = model.complete(ENRICHMENT_SYSTEM, user)
    return write_section(case, result, EnrichmentSection, "enrichment")
