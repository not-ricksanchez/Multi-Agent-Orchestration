import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from underwriting.models import OllamaIntakeAdapter, OllamaModelAdapter
from underwriting.orchestrator import run_case
from underwriting.summary import summarize_trace
from underwriting.tracing import Tracer

APP_TIMEOUT = {
    "case_id": "app-timeout",
    "applicant_name": "Ada Lovelace",
    "license_number": "D1002001",
    "age": 40,
    "years_licensed": 20,
    "vehicle_year": 2018,
    "vehicle_make": "Honda",
    "coverage_amount": 500000,
    "prior_claims": 0,
}


def main() -> None:
    os.chdir(ROOT)
    tracer = Tracer()
    print(f"run_id={tracer.run_id} traces={tracer.run_directory}")
    case = run_case(
        APP_TIMEOUT, OllamaModelAdapter(), tracer, intake_model=OllamaIntakeAdapter()
    )
    path = tracer.path_for(case["case_id"])
    for span in json.loads(path.read_text()):
        error = span["error"]["type"] if span["error"] else None
        print(
            f"{span['agent']} attempt={span['attempt']} status={span['status']} "
            f"decision={span['decision']} error={error}"
        )
    summary = summarize_trace(path)
    print(
        f"status={case['status']} failure={case['failure']} "
        f"cost_usd={summary['cost_usd']} duration_ms={summary['duration_ms']}"
    )
    if case["status"] != "escalated" or case["risk"] or case["recommendation"]:
        raise SystemExit("app-timeout was not escalated cleanly")


if __name__ == "__main__":
    main()
