import json
import uuid
from datetime import datetime, timezone
from pathlib import Path


def new_run_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{stamp}-{uuid.uuid4().hex[:6]}"


class Tracer:
    def __init__(self, directory: str | Path = "traces", run_id: str | None = None):
        self.run_id = run_id or new_run_id()
        self.run_directory = Path(directory) / self.run_id

    def path_for(self, case_id: str) -> Path:
        return self.run_directory / f"{case_id}.json"

    def record(self, span: dict) -> None:
        self.run_directory.mkdir(parents=True, exist_ok=True)
        path = self.path_for(span["case_id"])
        spans = json.loads(path.read_text()) if path.exists() else []
        spans.append({"run_id": self.run_id, **span})
        path.write_text(json.dumps(spans, indent=2) + "\n")
