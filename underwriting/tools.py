import json
from pathlib import Path

from underwriting.errors import BureauError

DEFAULT_BUREAU_PATH = Path(__file__).resolve().parents[1] / "bureau_reports.json"


def lookup_bureau(intake: dict, path: str | Path) -> dict:
    license_number = intake["license_number"]
    try:
        with open(path, encoding="utf-8") as handle:
            reports = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise BureauError(f"cannot read bureau file {path}: {exc}") from exc
    if not isinstance(reports, list) or not all(
        isinstance(report, dict) and "license_number" in report for report in reports
    ):
        raise BureauError(
            f"bureau file {path} is not a list of reports with license_number"
        )
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
