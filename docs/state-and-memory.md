# State and memory

The pipeline keeps one shared case record per application. The orchestrator owns that record. It is a plain Python dict in memory. Agents read the sections they are allowed to see, validate their model reply, and write only their own section.

## Why message passing was rejected

Later steps and escalation need the whole file.

Enrichment needs the intake section. Risk scoring needs intake and enrichment. Recommendation needs intake, enrichment, and risk. A message that carries only the previous agent's output drops everything earlier in the file, so those steps cannot run from a handoff alone.

Escalation needs the whole file too. When an agent times out or returns invalid output, that section and every later section stay empty, and the case records which agent stopped the work. That outcome is a property of the shared record, not of a message between two agents.

## Case record

`new_case(raw)` builds the record. `raw` is one application dictionary. In the live batch that dictionary comes from a CSV row. In tests it is built inline. The orchestrator stores it on `raw_application`.

```python
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
```

Agents mutate this dict and return it. Sections stay disjoint. A section stays `None` until that agent's validation succeeds. Only `run_case` writes `status` and `failure`.

`_last_usage` is a temporary key an agent may set so the orchestrator can price the span. The orchestrator moves it onto the trace and deletes it. It is not part of the stored case.

## What this store is not

`applications.csv` is the inbound batch. Intake does not open it. The loader turns each row into a dictionary, and `run_case` copies that dictionary onto `raw_application`.

`bureau_reports.json` is the vendor file. `lookup_bureau` reads it by `license_number`. It is not the case store. The enrichment section is the mapped result of that report. `run_case` looks the report up once and passes that same dictionary to `enrichment_agent`, so the `mock_bureau` span shows exactly the report the model saw.

Every application is personal auto. There is no home product.

## Read and write contract

Each agent prompts only with the sections it is allowed to read. It writes `model_dump()` only after `model_validate` succeeds. An invalid reply leaves that section `None`.

### intake_agent

Reads `raw_application`. Source: `user`.

Writes `intake`:

- `applicant_name`
- `license_number`
- `age`
- `years_licensed`
- `vehicle_year`
- `vehicle_make`
- `coverage_amount`
- `prior_claims`
- `missing_fields`

Intake only normalizes the form.

### enrichment_agent

Reads `intake` (source `intake_agent`) and the bureau report passed in by `run_case` (source `mock_bureau`, from `lookup_bureau(intake, path)` on `bureau_reports.json`). The agent does not open the file itself.

Writes `enrichment`:

- `credit_band`: `excellent`, `fair`, `poor`, or `unknown`
- `loss_history`: `at_fault_accidents`, `violations`, and `total_losses`, or `null`
- `vehicle_symbol`: int or `null`
- `garaging_risk`: `low`, `high`, or `unknown`
- `flags`: list of strings
- `source`: `mock_bureau`

The prompt includes the vendor report, the intake section, and the mapping rules below. Enrichment does not restate intake fields. The model maps the report. It does not invent vendor fields.

Mapping rules:

- Credit score `750` or above is `excellent`. `650`–`749` is `fair`. `1`–`649` is `poor`. Null is `unknown`.
- `at_fault_accidents` counts events of type `at_fault_accident`. `violations` counts `major_violation` and `minor_violation`. `total_losses` is the number of events. An empty `mvr_events` list gives all zeros. Null `mvr_events` makes `loss_history` null.
- `iso_symbol` is copied to `vehicle_symbol`.
- Territory `suburban` or `rural` is garaging `low`. `urban` is `high`. Null is `unknown`.
- Flags: `recent_at_fault` if any at-fault event, `major_violations` if any major violation, `incomplete_bureau` only if credit score or events are null or the report is `NOT_FOUND`. Otherwise `[]`.
- `source` is `mock_bureau`.

Checked-in reports, one object per `license_number`:

| License | Case | Report | Credit | Events | ISO | Territory |
| --- | --- | --- | --- | --- | --- | --- |
| `D1002001` | `APP-1001` | `R-1001` | 790 | none | 12 | `suburban` |
| `D1002002` | `APP-1002` | `R-1002` | 540 | two `at_fault_accident`, three `major_violation` | 28 | `urban` |
| `D1002003` | `APP-1003` | `R-1003` | null | null | null | null |

Each report has `report_id`, `pulled_at`, `license_number`, `credit_score`, `mvr_events`, `iso_symbol`, and `garaging_territory`. `mvr_events` is a list of `{type, date}` or null. Event types are `at_fault_accident`, `major_violation`, and `minor_violation`. `garaging_territory` is `suburban`, `rural`, `urban`, or null. All three reports are pulled `2026-10-01`.

A missing license returns `report_id` `NOT_FOUND` and nulls for `pulled_at`, `credit_score`, `mvr_events`, `iso_symbol`, and `garaging_territory`.

### risk_scoring_agent

Reads `intake` and `enrichment`. Sources: `intake_agent` and `enrichment_agent`.

Writes `risk`:

- `score`: integer from 0 to 100
- `drivers`: list of strings
- `missing_data`: bool

The prompt tells the model to use bureau flags, credit, and loss history, not only the form.

Case id `app-timeout` makes this agent raise `TimeoutError` before any model call. That call does not write `risk`. The `app-timeout` test application uses license `D1002001`, so enrichment can load a real report and only risk scoring fails. `app-timeout` is not in the CSV.

### recommendation_agent

Reads `intake`, `enrichment`, and `risk`. Sources: `intake_agent`, `enrichment_agent`, and `risk_scoring_agent`.

Writes `recommendation`:

- `decision`: `approve`, `deny`, or `refer`
- `reason`: string

The prompt applies the rules in order and stops at the first match: deny on poor credit, `recent_at_fault`, `major_violations`, or 3 or more prior claims; refer on missing data, unknown credit, null loss history, `incomplete_bureau`, or any `missing_fields`; approve on excellent or fair credit, no at-fault accidents, at most one violation, and a risk score of 60 or lower; otherwise refer.

If `risk` is missing, this agent raises `ValueError` and does not call the model. It does not invent a decision, and `recommendation` stays `None`.

### run_case

The orchestrator is plain Python. It does not call the model.

It calls the four agents in order: intake, enrichment, risk scoring, recommendation. Around each call it records a trace span from the sections read and written.

On the happy path it sets `status` to `complete` after recommendation.

A timeout or an invalid reply retries that same agent, then escalates. Escalation sets `status` to `escalated`, sets `failure` to the agent name, the error type (`TimeoutError` or `ValidationError`), and the attempt count, leaves the failed section and every later section as `None`, and skips the remaining agents. Every attempt writes its own trace span with `attempt`, `status` (`ok`, `retry`, or `escalated` on the last failed attempt), and `error` (`type` and `message`). A failed attempt has a null `output`. A `ValidationError` attempt keeps its model tokens and `cost_usd`, because the model did reply. Escalation adds one `orchestrator` span with `step` `escalation` and `decision` `escalate`. The required demonstration is `app-timeout` on risk scoring: `risk` and `recommendation` stay `None`.
