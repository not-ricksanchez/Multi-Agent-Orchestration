import json
import re

from underwriting.tracing import Tracer


def test_tracer_writes_spans_under_its_run_directory(tmp_path):
    tracer = Tracer(tmp_path, run_id="20261011T201500Z-abc123")

    tracer.record({"case_id": "APP-1001", "step": "intake"})
    tracer.record({"case_id": "APP-1001", "step": "risk"})

    path = tmp_path / "20261011T201500Z-abc123" / "APP-1001.json"
    assert tracer.path_for("APP-1001") == path
    spans = json.loads(path.read_text())
    assert [span["step"] for span in spans] == ["intake", "risk"]
    assert {span["run_id"] for span in spans} == {"20261011T201500Z-abc123"}


def test_two_runs_do_not_share_a_trace_file(tmp_path):
    first = Tracer(tmp_path)
    second = Tracer(tmp_path)

    first.record({"case_id": "APP-1001", "step": "intake"})
    second.record({"case_id": "APP-1001", "step": "intake"})

    assert first.run_id != second.run_id
    assert re.fullmatch(r"\d{8}T\d{6}Z-[0-9a-f]{6}", first.run_id)
    assert len(json.loads(first.path_for("APP-1001").read_text())) == 1
    assert len(json.loads(second.path_for("APP-1001").read_text())) == 1
