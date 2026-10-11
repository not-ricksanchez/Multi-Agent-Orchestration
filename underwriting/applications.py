import csv
from pathlib import Path

NUMERIC_COLUMNS = {
    "age",
    "years_licensed",
    "vehicle_year",
    "coverage_amount",
    "prior_claims",
}


def load_applications(path: str | Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as handle:
        applications = []
        for row in csv.DictReader(handle):
            application = {}
            for key, value in row.items():
                if value is None or value.strip() == "":
                    continue
                application[key] = int(value) if key in NUMERIC_COLUMNS else value
            applications.append(application)
        return applications
