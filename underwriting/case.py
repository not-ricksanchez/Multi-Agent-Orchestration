def new_case(raw: dict) -> dict:
    return {
        "case_id": raw["case_id"],
        "raw_application": raw,
        "intake": None,
        "enrichment": None,
        "risk": None,
        "recommendation": None,
        "status": "in_progress",
        "failure": None,
    }
