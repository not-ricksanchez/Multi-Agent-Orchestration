import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from underwriting.applications import load_applications
from underwriting.models import OllamaModelAdapter
from underwriting.orchestrator import run_case
from underwriting.summary import summarize_trace
from underwriting.tracing import Tracer


def main() -> None:
    os.chdir(ROOT)
    applications = load_applications("applications.csv")
    model = OllamaModelAdapter()
    tracer = Tracer()
    print(f"run_id={tracer.run_id} traces={tracer.run_directory}")
    total_cost = 0.0
    total_duration = 0
    for raw in applications:
        case = run_case(raw, model, tracer)
        summary = summarize_trace(tracer.path_for(case["case_id"]))
        total_cost += summary["cost_usd"]
        total_duration += summary["duration_ms"]
        decision = case["recommendation"]["decision"] if case["recommendation"] else None
        print(
            f"{case['case_id']} decision={decision} "
            f"cost_usd={summary['cost_usd']} duration_ms={summary['duration_ms']}"
        )
        if case["status"] != "complete" or decision is None:
            raise SystemExit(f"{case['case_id']} did not complete")
    print(f"total cost_usd={total_cost} duration_ms={total_duration}")


if __name__ == "__main__":
    main()
