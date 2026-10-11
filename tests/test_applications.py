from pathlib import Path

from underwriting.applications import load_applications

CSV = Path(__file__).resolve().parents[1] / "applications.csv"


def test_load_applications_returns_three_integer_ages():
    rows = load_applications(CSV)

    assert [row["case_id"] for row in rows] == ["APP-1001", "APP-1002", "APP-1003"]
    assert [row["age"] for row in rows] == [40, 18, 35]
    assert all(isinstance(row["age"], int) for row in rows)
    assert rows[0]["prior_claims"] == 0
    assert rows[0]["years_licensed"] == 20
    assert rows[0]["coverage_amount"] == 500000
    assert "prior_claims" not in rows[2]
    assert "app-timeout" not in {row["case_id"] for row in rows}
