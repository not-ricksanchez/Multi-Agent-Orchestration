# Failure handling

## The injected failure

`risk_scoring_agent` raises `TimeoutError("simulated risk-scoring timeout")` when `case_id` is `app-timeout`. It raises before the model call, so no tokens are spent and `risk` is never written. The test application uses license `D1002001`, so intake and enrichment run normally against a real bureau report and only risk scoring fails. `app-timeout` is not in `applications.csv`.

## The handling: retry, then escalate

`run_case` wraps every agent in the same loop.

- `TimeoutError`, `pydantic.ValidationError`, `ModelResponseError`, and `ConnectionError` are retried. Each failed attempt leaves that agent's section `None`.
- `OllamaModelAdapter` raises those types for real faults. It passes a 120 s `timeout` to `urlopen`, so a hung call raises `TimeoutError`. An unreachable server raises `ConnectionError`. A reply that is not a JSON object raises `ModelResponseError`.
- Up to `max_attempts` (3) attempts, with a wait of `0.5 * attempt` seconds between them: 0.5 s, then 1.0 s.
- When the last attempt fails, the case is escalated: `status` becomes `escalated`, `failure` names the agent, the error type, and the attempt count, and every later agent is skipped. No recommendation is produced.
- `run_case` returns the case. The exception does not reach the caller.
- The bureau lookup is not retried, because a missing or broken file will not fix itself. `lookup_bureau` raises `BureauError` when `bureau_reports.json` is missing, is not valid JSON, or is not a list of reports with `license_number`. `run_case` records a `mock_bureau` span with status `escalated` and the error, then escalates at once with `failure` `{"agent": "mock_bureau", "error": "BureauError", "attempts": 1}`. Enrichment, risk, and recommendation are skipped. A license that is simply absent from the file is not an error: it returns a `NOT_FOUND` report and the case continues.

A human underwriter picks up an `escalated` case. That is different from `refer`, which is a completed recommendation on a thin file.

## Trace evidence

Produced by `scripts/run_timeout_case.py`. The live adapter default is `qwen3:8b` with `think` false. The checked-in demonstration is run `20261012T010200Z-120d74` (`traces/20261012T010200Z-120d74/app-timeout.json`). Intake ran on `qwen3:4b` and enrichment on `qwen3:8b`; the timeout path does not call the model.


| Step        | Agent              | Model      | Attempt | Status    | Error        | Started (UTC) | duration_ms | cost_usd |
| ----------- | ------------------ | ---------- | ------- | --------- | ------------ | ------------- | ----------- | -------- |
| intake      | intake_agent       | `qwen3:4b` | 1       | ok        |              | 01:02:00.149  | 4,073       | 0.000424 |
| mock_bureau | mock_bureau        |            | 1       | ok        |              | 01:02:04.226  | 0           |          |
| enrichment  | enrichment_agent   | `qwen3:8b` | 1       | ok        |              | 01:02:04.227  | 6,830       | 0.001472 |
| risk        | risk_scoring_agent | `qwen3:8b` | 1       | retry     | TimeoutError | 01:02:11.068  | 0           |          |
| risk        | risk_scoring_agent | `qwen3:8b` | 2       | retry     | TimeoutError | 01:02:11.571  | 0           |          |
| risk        | risk_scoring_agent | `qwen3:8b` | 3       | escalated | TimeoutError | 01:02:12.576  | 0           |          |
| escalation  | orchestrator       |            | 3       | escalated | TimeoutError | 01:02:12.579  | 0           |          |


The start times show the backoff: about 0.5 s between attempts 1 and 2, and 1.0 s between attempts 2 and 3. The escalation span has `decision` `escalate` and output `{"status": "escalated", "failure": {"agent": "risk_scoring_agent", "error": "TimeoutError", "attempts": 3}}`.

The final case has `intake` and `enrichment` filled, and `risk` and `recommendation` both `None`. Only intake and enrichment called the model, so the case cost $0.001896. The failed risk spans have no tokens or cost, because the timeout is raised before any model call. Span durations sum to 10,903 ms. The 1.5 s of backoff waits are not inside any span.

## Outcome

- No crash: the script exits normally and the case is returned.
- No silent wrong answer: there is no risk score and no recommendation, and the case is marked `escalated` with the failing agent named.
- Every attempt is visible in the trace, with its error.



## Tests

`tests/test_failure.py` runs without Ollama.

- `app-timeout` retries risk scoring three times, escalates, and leaves `risk` and `recommendation` `None`. The scripted adapter is called only for intake and enrichment.
- A risk reply that fails schema validation three times escalates with `failure["error"] == "ValidationError"`. Each failed span keeps its tokens and cost, because the model did reply.
- One invalid risk reply followed by a valid one recovers: one `retry` span, then `ok`, and the case completes with a recommendation.
- An enrichment call that raises `ModelResponseError` or `ConnectionError` three times escalates on `enrichment_agent`. The failed spans have no tokens or cost, because no reply was parsed.
- One `ConnectionError` on intake followed by a good reply recovers and completes.
- A missing, non-JSON, or wrongly shaped bureau file escalates on `mock_bureau` after one attempt, with no waits and no enrichment call. `tests/test_tools.py` checks that `lookup_bureau` raises `BureauError` in each of those cases.

`tests/test_models.py` checks that the adapter passes its timeout to `urlopen` and maps a timed-out call to `TimeoutError`, an unreachable server to `ConnectionError`, and a non-JSON reply to `ModelResponseError`.

## Not covered

Other exceptions are not retried and reach the caller. That includes the `ValueError` that `recommendation_agent` raises when `risk` is missing. Escalation skips recommendation whenever risk fails, so that `ValueError` is not reached from `run_case`.