import json
from pathlib import Path


class Tracer:
    def __init__(self, directory: str | Path = "traces"):
        self.directory = Path(directory)

    def record(self, span: dict) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / f"{span['case_id']}.json"
        spans = json.loads(path.read_text()) if path.exists() else []
        spans.append(span)
        path.write_text(json.dumps(spans, indent=2) + "\n")
