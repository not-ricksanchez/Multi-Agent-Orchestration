import json
from pathlib import Path


def lookup_bureau(intake: dict, path: str | Path) -> dict:
    license_number = intake["license_number"]
    with open(path, encoding="utf-8") as handle:
        reports = json.load(handle)
    for report in reports:
        if report["license_number"] == license_number:
            return report
    return {
        "report_id": "NOT_FOUND",
        "pulled_at": None,
        "license_number": license_number,
        "credit_score": None,
        "mvr_events": None,
        "iso_symbol": None,
        "garaging_territory": None,
    }
