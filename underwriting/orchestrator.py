import time
from datetime import datetime, timezone

from underwriting.agents.enrichment import DEFAULT_BUREAU_PATH, enrichment_agent
from underwriting.agents.intake import intake_agent
from underwriting.case import new_case
from underwriting.pricing import cost_usd
from underwriting.tools import lookup_bureau
from underwriting.tracing import Tracer


def run_case(
    raw: dict,
    model,
    tracer: Tracer,
    *,
    max_attempts: int = 3,
    sleep=time.sleep,
) -> dict:
    case = new_case(raw)
    _record_model_step(
        case,
        tracer,
        agent="intake_agent",
        step="intake",
        call=lambda: intake_agent(case, model),
        recorded_input={"raw_application": case["raw_application"]},
        input_source=[{"field": "raw_application", "from": "user"}],
        output_key="intake",
        max_attempts=max_attempts,
    )
    started_at, started = _clock()
    report = lookup_bureau(case["intake"], DEFAULT_BUREAU_PATH)
    tracer.record(
        _span(
            case,
            step="mock_bureau",
            agent="mock_bureau",
            recorded_input={"intake": case["intake"]},
            input_source=[{"field": "intake", "from": "intake_agent"}],
            output=report,
            started_at=started_at,
            duration_ms=_duration_ms(started),
            model=None,
            usage=None,
            cost=None,
            max_attempts=max_attempts,
        )
    )
    _record_model_step(
        case,
        tracer,
        agent="enrichment_agent",
        step="enrichment",
        call=lambda: enrichment_agent(case, model),
        recorded_input={"intake": case["intake"], "bureau_report": report},
        input_source=[
            {"field": "intake", "from": "intake_agent"},
            {"field": "bureau_report", "from": "mock_bureau"},
        ],
        output_key="enrichment",
        max_attempts=max_attempts,
    )
    return case


def _record_model_step(
    case,
    tracer,
    *,
    agent,
    step,
    call,
    recorded_input,
    input_source,
    output_key,
    max_attempts,
):
    started_at, started = _clock()
    call()
    usage = case.pop("_last_usage")
    tracer.record(
        _span(
            case,
            step=step,
            agent=agent,
            recorded_input=recorded_input,
            input_source=input_source,
            output=case[output_key],
            started_at=started_at,
            duration_ms=_duration_ms(started),
            model=usage["model"],
            usage={
                "input_tokens": usage["input_tokens"],
                "output_tokens": usage["output_tokens"],
            },
            cost=cost_usd(usage["input_tokens"], usage["output_tokens"]),
            max_attempts=max_attempts,
        )
    )


def _span(
    case,
    *,
    step,
    agent,
    recorded_input,
    input_source,
    output,
    started_at,
    duration_ms,
    model,
    usage,
    cost,
    max_attempts,
) -> dict:
    return {
        "case_id": case["case_id"],
        "step": step,
        "agent": agent,
        "input": recorded_input,
        "input_source": input_source,
        "output": output,
        "decision": None,
        "started_at": started_at,
        "duration_ms": duration_ms,
        "model": model,
        "usage": usage,
        "cost_usd": cost,
        "attempt": 1,
        "max_attempts": max_attempts,
        "status": "ok",
        "error": None,
    }


def _clock():
    return datetime.now(timezone.utc).isoformat(), time.perf_counter()


def _duration_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)
