from pathlib import Path

import pytest

from underwriting.errors import BureauError
from underwriting.tools import lookup_bureau

BUREAU = Path(__file__).resolve().parents[1] / "bureau_reports.json"


def test_lookup_bureau_returns_clean_report():
    report = lookup_bureau({"license_number": "D1002001"}, BUREAU)

    assert report["report_id"] == "R-1001"
    assert report["pulled_at"] == "2026-10-01"
    assert report["license_number"] == "D1002001"
    assert report["credit_score"] == 790
    assert report["mvr_events"] == []
    assert report["iso_symbol"] == 12
    assert report["garaging_territory"] == "suburban"


def test_lookup_bureau_returns_risky_report():
    report = lookup_bureau({"license_number": "D1002002"}, BUREAU)

    assert report["report_id"] == "R-1002"
    assert report["pulled_at"] == "2026-10-01"
    assert report["credit_score"] == 540
    assert report["iso_symbol"] == 28
    assert report["garaging_territory"] == "urban"
    event_types = [event["type"] for event in report["mvr_events"]]
    assert event_types.count("at_fault_accident") == 2
    assert event_types.count("major_violation") == 3
    assert all("date" in event for event in report["mvr_events"])


def test_lookup_bureau_returns_thin_report():
    report = lookup_bureau({"license_number": "D1002003"}, BUREAU)

    assert report["report_id"] == "R-1003"
    assert report["pulled_at"] == "2026-10-01"
    assert report["license_number"] == "D1002003"
    assert report["credit_score"] is None
    assert report["mvr_events"] is None
    assert report["iso_symbol"] is None
    assert report["garaging_territory"] is None


def test_lookup_bureau_unknown_license_is_not_found():
    report = lookup_bureau({"license_number": "D0000000"}, BUREAU)

    assert report["report_id"] == "NOT_FOUND"
    assert report["pulled_at"] is None
    assert report["credit_score"] is None
    assert report["mvr_events"] is None
    assert report["iso_symbol"] is None
    assert report["garaging_territory"] is None


def test_lookup_bureau_missing_file_raises_bureau_error(tmp_path):
    with pytest.raises(BureauError, match="cannot read"):
        lookup_bureau({"license_number": "D1002001"}, tmp_path / "missing.json")


def test_lookup_bureau_invalid_json_raises_bureau_error(tmp_path):
    path = tmp_path / "bureau.json"
    path.write_text("[{not json")

    with pytest.raises(BureauError, match="cannot read"):
        lookup_bureau({"license_number": "D1002001"}, path)


@pytest.mark.parametrize(
    "contents",
    ['{"license_number": "D1002001"}', '["R-1001"]', '[{"report_id": "R-1001"}]'],
)
def test_lookup_bureau_wrong_shape_raises_bureau_error(tmp_path, contents):
    path = tmp_path / "bureau.json"
    path.write_text(contents)

    with pytest.raises(BureauError, match="list of reports"):
        lookup_bureau({"license_number": "D1002001"}, path)
