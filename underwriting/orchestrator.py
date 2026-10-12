import time
from datetime import datetime, timezone

from pydantic import ValidationError

from underwriting.agents.enrichment import enrichment_agent
from underwriting.agents.intake import intake_agent
from underwriting.agents.recommendation import recommendation_agent
from underwriting.agents.risk import risk_scoring_agent
from underwriting.case import new_case
from underwriting.errors import BureauError, ModelResponseError
from underwriting.pricing import cost_usd
from underwriting.tools import DEFAULT_BUREAU_PATH, lookup_bureau
from underwriting.tracing import Tracer

RETRYABLE = (TimeoutError, ValidationError, ModelResponseError, ConnectionError)


class _Escalated(Exception):
    pass


def run_case(
    raw: dict,
    model,
    tracer: Tracer,
    *,
    max_attempts: int = 3,
    sleep=time.sleep,
    bureau_path=DEFAULT_BUREAU_PATH,
    intake_model=None,
) -> dict:
    case = new_case(raw)
    try:
        _run_steps(
            case, model, tracer, max_attempts, sleep, bureau_path, intake_model or model
        )
    except _Escalated:
        return case
    case["status"] = "complete"
    return case


def _run_steps(case, model, tracer, max_attempts, sleep, bureau_path, intake_model):
    _record_model_step(
        case,
        tracer,
        agent="intake_agent",
        adapter=intake_model,
        step="intake",
        call=lambda: intake_agent(case, intake_model),
        recorded_input={"raw_application": case["raw_application"]},
        input_source=[{"field": "raw_application", "from": "user"}],
        output_key="intake",
        max_attempts=max_attempts,
        sleep=sleep,
    )
    report = _lookup_bureau_step(case, tracer, bureau_path)
    _record_model_step(
        case,
        tracer,
        agent="enrichment_agent",
        adapter=model,
        step="enrichment",
        call=lambda: enrichment_agent(case, model, report),
        recorded_input={"intake": case["intake"], "bureau_report": report},
        input_source=[
            {"field": "intake", "from": "intake_agent"},
            {"field": "bureau_report", "from": "mock_bureau"},
        ],
        output_key="enrichment",
        max_attempts=max_attempts,
        sleep=sleep,
    )
    _record_model_step(
        case,
        tracer,
        agent="risk_scoring_agent",
        adapter=model,
        step="risk",
        call=lambda: risk_scoring_agent(case, model),
        recorded_input={"intake": case["intake"], "enrichment": case["enrichment"]},
        input_source=[
            {"field": "intake", "from": "intake_agent"},
            {"field": "enrichment", "from": "enrichment_agent"},
        ],
        output_key="risk",
        max_attempts=max_attempts,
        sleep=sleep,
    )
    _record_model_step(
        case,
        tracer,
        agent="recommendation_agent",
        adapter=model,
        step="recommendation",
        call=lambda: recommendation_agent(case, model),
        recorded_input={
            "intake": case["intake"],
            "enrichment": case["enrichment"],
            "risk": case["risk"],
        },
        input_source=[
            {"field": "intake", "from": "intake_agent"},
            {"field": "enrichment", "from": "enrichment_agent"},
            {"field": "risk", "from": "risk_scoring_agent"},
        ],
        output_key="recommendation",
        max_attempts=max_attempts,
        sleep=sleep,
    )


def _lookup_bureau_step(case, tracer, bureau_path):
    started_at, started = _clock()
    span = dict(
        step="mock_bureau",
        agent="mock_bureau",
        recorded_input={"intake": case["intake"]},
        input_source=[{"field": "intake", "from": "intake_agent"}],
        started_at=started_at,
        model=None,
        usage=None,
        cost=None,
        max_attempts=1,
    )
    try:
        report = lookup_bureau(case["intake"], bureau_path)
    except BureauError as exc:
        tracer.record(
            _span(
                case,
                **span,
                output=None,
                duration_ms=_duration_ms(started),
                status="escalated",
                error=_error(exc),
            )
        )
        _escalate(case, tracer, "mock_bureau", "bureau_report", exc, max_attempts=1)
        raise _Escalated from exc
    tracer.record(
        _span(case, **span, output=report, duration_ms=_duration_ms(started))
    )
    return report


def _record_model_step(
    case,
    tracer,
    *,
    agent,
    adapter,
    step,
    call,
    recorded_input,
    input_source,
    output_key,
    max_attempts,
    sleep,
):
    model_name = getattr(adapter, "model", None)
    for attempt in range(1, max_attempts + 1):
        started_at, started = _clock()
        try:
            call()
        except RETRYABLE as exc:
            duration_ms = _duration_ms(started)
            final = attempt == max_attempts
            tracer.record(
                _span(
                    case,
                    step=step,
                    agent=agent,
                    recorded_input=recorded_input,
                    input_source=input_source,
                    output=None,
                    started_at=started_at,
                    duration_ms=duration_ms,
                    max_attempts=max_attempts,
                    attempt=attempt,
                    status="escalated" if final else "retry",
                    error=_error(exc),
                    **_usage_fields(case.pop("_last_usage", None), model_name),
                )
            )
            if final:
                _escalate(case, tracer, agent, output_key, exc, max_attempts)
                raise _Escalated from exc
            sleep(0.5 * attempt)
            continue
        output = case[output_key]
        tracer.record(
            _span(
                case,
                step=step,
                agent=agent,
                recorded_input=recorded_input,
                input_source=input_source,
                output=output,
                started_at=started_at,
                duration_ms=_duration_ms(started),
                max_attempts=max_attempts,
                attempt=attempt,
                decision=output.get("decision"),
                **_usage_fields(case.pop("_last_usage"), model_name),
            )
        )
        return


def _escalate(case, tracer, agent, output_key, exc, max_attempts):
    started_at, started = _clock()
    case["status"] = "escalated"
    case["failure"] = {
        "agent": agent,
        "error": type(exc).__name__,
        "attempts": max_attempts,
    }
    tracer.record(
        _span(
            case,
            step="escalation",
            agent="orchestrator",
            recorded_input={"failure": case["failure"]},
            input_source=[{"field": output_key, "from": agent}],
            output={"status": "escalated", "failure": case["failure"]},
            started_at=started_at,
            duration_ms=_duration_ms(started),
            model=None,
            usage=None,
            cost=None,
            max_attempts=max_attempts,
            attempt=max_attempts,
            status="escalated",
            error=_error(exc),
            decision="escalate",
        )
    )


def _usage_fields(usage, model_name=None):
    if usage is None:
        return {"model": model_name, "usage": None, "cost": None}
    return {
        "model": usage["model"],
        "usage": {
            "input_tokens": usage["input_tokens"],
            "output_tokens": usage["output_tokens"],
        },
        "cost": cost_usd(usage["input_tokens"], usage["output_tokens"], usage["model"]),
    }


def _error(exc) -> dict:
    return {"type": type(exc).__name__, "message": str(exc)}


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
    attempt=1,
    status="ok",
    error=None,
    decision=None,
) -> dict:
    return {
        "case_id": case["case_id"],
        "step": step,
        "agent": agent,
        "input": recorded_input,
        "input_source": input_source,
        "output": output,
        "decision": decision,
        "started_at": started_at,
        "duration_ms": duration_ms,
        "model": model,
        "usage": usage,
        "cost_usd": cost,
        "attempt": attempt,
        "max_attempts": max_attempts,
        "status": status,
        "error": error,
    }


def _clock():
    return datetime.now(timezone.utc).isoformat(), time.perf_counter()


def _duration_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)
