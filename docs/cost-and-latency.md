# Cost and latency

These figures come from `summarize_trace` on the three files written by `scripts/run_three_cases.py`, run `20261012T005624Z-3e4151` (`traces/20261012T005624Z-3e4151/`). Intake runs on `qwen3:4b`. Enrichment, risk, and recommendation run on `qwen3:8b`. Both use `think` false. Each run writes to its own `traces/<run_id>/` directory, so a re-run never mixes spans into an earlier run's files. The script does not overwrite the model's decision.

The dollar amounts are faked. Both models ran locally through Ollama, which does not bill per token. The prices below are used to **mock** the cost here, used only to show what the same token counts would cost if this pipeline called a paid model.

Prices, applied per span from the model name stored on that span (`underwriting/pricing.py`):


| Model                                         | Input, per million tokens | Output, per million tokens |
| --------------------------------------------- | ------------------------- | -------------------------- |
| `qwen3:4b` (intake)                           | $0.50                     | $1.00                      |
| `qwen3:8b` (enrichment, risk, recommendation) | $1.00                     | $2.00                      |


```text
cost_usd = (input_tokens * input_price + output_tokens * output_price) / 1_000_000
```

A model that is not in the table, such as the scripted adapter in the tests, is priced like `qwen3:8b`.

The bureau lookup is not a model call, so it is omitted from these tables. Its duration was 0 to 1 ms on each file.

Summary per case. Tokens are input plus output, and cost is the mock cost:


| Case     | Intake ms | Enrichment ms | Risk ms | Recommendation ms | Total ms | Tokens | Cost      |
| -------- | --------- | ------------- | ------- | ----------------- | -------- | ------ | --------- |
| APP-1001 | 3313      | 4775          | 2785    | 5215              | 16088    | 3545   | $0.003405 |
| APP-1002 | 3184      | 6281          | 4517    | 4302              | 18284    | 3734   | $0.003622 |
| APP-1003 | 3395      | 3849          | 2444    | 3138              | 12826    | 3443   | $0.003249 |


Per agent:


| Case     | Agent           | Model    | Input tokens | Output tokens | duration_ms | duration_s | cost_usd |
| -------- | --------------- | -------- | ------------ | ------------- | ----------- | ---------- | -------- |
| APP-1001 | intake          | qwen3:4b | 662          | 94            | 3,313       | 3.3        | 0.000425 |
| APP-1001 | enrichment      | qwen3:8b | 1,314        | 79            | 4,775       | 4.8        | 0.001472 |
| APP-1001 | risk            | qwen3:8b | 701          | 32            | 2,785       | 2.8        | 0.000765 |
| APP-1001 | recommendation  | qwen3:8b | 583          | 80            | 5,215       | 5.2        | 0.000743 |
| APP-1001 | total (approve) |          | 3,260        | 285           | 16,088      | 16.1       | 0.003405 |
| APP-1002 | intake          | qwen3:4b | 660          | 92            | 3,184       | 3.2        | 0.000422 |
| APP-1002 | enrichment      | qwen3:8b | 1,431        | 89            | 6,281       | 6.3        | 0.001609 |
| APP-1002 | risk            | qwen3:8b | 709          | 65            | 4,517       | 4.5        | 0.000839 |
| APP-1002 | recommendation  | qwen3:8b | 624          | 64            | 4,302       | 4.3        | 0.000752 |
| APP-1002 | total (deny)    |          | 3,424        | 310           | 18,284      | 18.3       | 0.003622 |
| APP-1003 | intake          | qwen3:4b | 653          | 96            | 3,395       | 3.4        | 0.000423 |
| APP-1003 | enrichment      | qwen3:8b | 1,310        | 54            | 3,849       | 3.8        | 0.001418 |
| APP-1003 | risk            | qwen3:8b | 684          | 33            | 2,444       | 2.4        | 0.000750 |
| APP-1003 | recommendation  | qwen3:8b | 567          | 46            | 3,138       | 3.1        | 0.000659 |
| APP-1003 | total (refer)   |          | 3,214        | 229           | 12,826      | 12.8       | 0.003249 |
| Batch    |                 |          | 9,898        | 824           | 47,198      | 47.2       | 0.010277 |


The batch cost at those assumed rates is about one cent. Each application is a fraction of a cent. Latency is still what rules out real time. Four sequential local calls with thinking off took 13 to 18 seconds per file, and the three files together took 47,198 ms. A bind-now response still cannot wait 13 to 18 s. The same sequence belongs on an overnight or asynchronous batch.

## Why intake runs on `qwen3:4b`

Intake only normalizes the form, so it is the one step a smaller model can do. With all four agents on `qwen3:8b` (run `20261011T231927Z-aa3f6c`), intake took 6.0 to 6.4 s per file and was the slowest step for the least work. Moving it to `qwen3:4b`:


|                              | All `qwen3:8b` | Intake on `qwen3:4b` | Change |
| ---------------------------- | -------------- | -------------------- | ------ |
| Intake duration, three files | 18,675 ms      | 9,892 ms             | -47%   |
| Batch duration               | 60,589 ms      | 47,198 ms            | -22%   |
| Batch cost (mock)            | $0.011564      | $0.010277            | -11%   |


Decisions are unchanged: approve, deny, refer.

Latency per agent, before and after the change. Before is run `20261011T231927Z-aa3f6c`, after is run `20261012T005624Z-3e4151`. Change is after minus before.


| Case     | Agent          | Model before | Model after | Before (ms) | After (ms) | Change (ms) | Change |
| -------- | -------------- | ------------ | ----------- | ----------- | ---------- | ----------- | ------ |
| APP-1001 | intake         | `qwen3:8b`   | `qwen3:4b`  | 6,235       | 3,313      | -2,922      | -47%   |
| APP-1001 | enrichment     | `qwen3:8b`   | `qwen3:8b`  | 5,037       | 4,775      | -262        | -5%    |
| APP-1001 | risk           | `qwen3:8b`   | `qwen3:8b`  | 3,856       | 2,785      | -1,071      | -28%   |
| APP-1001 | recommendation | `qwen3:8b`   | `qwen3:8b`  | 6,507       | 5,215      | -1,292      | -20%   |
| APP-1001 | total          |              |             | 21,635      | 16,088     | -5,547      | -26%   |
| APP-1002 | intake         | `qwen3:8b`   | `qwen3:4b`  | 6,000       | 3,184      | -2,816      | -47%   |
| APP-1002 | enrichment     | `qwen3:8b`   | `qwen3:8b`  | 6,714       | 6,281      | -433        | -6%    |
| APP-1002 | risk           | `qwen3:8b`   | `qwen3:8b`  | 4,616       | 4,517      | -99         | -2%    |
| APP-1002 | recommendation | `qwen3:8b`   | `qwen3:8b`  | 4,610       | 4,302      | -308        | -7%    |
| APP-1002 | total          |              |             | 21,940      | 18,284     | -3,656      | -17%   |
| APP-1003 | intake         | `qwen3:8b`   | `qwen3:4b`  | 6,440       | 3,395      | -3,045      | -47%   |
| APP-1003 | enrichment     | `qwen3:8b`   | `qwen3:8b`  | 4,197       | 3,849      | -348        | -8%    |
| APP-1003 | risk           | `qwen3:8b`   | `qwen3:8b`  | 2,788       | 2,444      | -344        | -12%   |
| APP-1003 | recommendation | `qwen3:8b`   | `qwen3:8b`  | 3,589       | 3,138      | -451        | -13%   |
| APP-1003 | total          |              |             | 17,014      | 12,826     | -4,188      | -25%   |
| Batch    | total          |              |             | 60,589      | 47,198     | -13,391     | -22%   |


Intake is the only step whose model changed, and it is faster on every case (-2,922, -2,816, and -3,045 ms, -8,783 ms in all, about 47% each). The other three steps use the same model and the same prompts, and their input and output token counts are identical to the earlier run, so their changes are run-to-run noise. They add up to -4,608 ms over the batch, so the batch saving of 13,391 ms is intake's 8,783 ms plus that noise.

The noise is not small, and it can go either way. An earlier run with the same setup (`20261012T003346Z-7fc7b0`) took intake from 18,675 ms to 11,835 ms and the batch from 60,589 ms to 54,224 ms (-11%), and its three unchanged steps came out 475 ms slower. Read together, intake saves about 1.7 to 3.0 s per case on every run, and the batch saving is 11% to 22% depending on the run.

Two things were needed to make `qwen3:4b` work, and both apply to intake only.

- **The schema is sent as Ollama's `format`.** With the plain `"format": "json"` request and the schema pasted in the prompt, `qwen3:4b` did not follow the schema. It echoed `{"raw_application": ...}` or the raw form back and never filled `missing_fields`. At temperature 0 all three retries returned the same reply, so every case escalated on intake. Passing `IntakeSection.model_json_schema()` as `format` made the reply valid and correct on all three applications. The prompt text is unchanged.
- **Its own price.** Spans record the model name, and `cost_usd` uses that model's rate, so the intake spans cost $0.50 / $1.00 per million tokens and the other spans cost $1 / $2.

