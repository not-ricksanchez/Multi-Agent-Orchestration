# Cost and latency

These figures come from `summarize_trace` on the three files written by `scripts/run_three_cases.py` against `gemma3:12b`, run `20261011T211553Z-78777c` (`traces/20261011T211553Z-78777c/`). Each run writes to its own `traces/<run_id>/` directory, so a re-run never mixes spans into an earlier run's files. The script does not overwrite the model's decision.

Price formula, stored on every model span:

```text
cost_usd = (input_tokens * 1 + output_tokens * 2) / 1_000_000
```

That is $1 per million input tokens and $2 per million output tokens. The bureau lookup is not a model call, so its `cost_usd` is null and it adds nothing to the sum. Its `duration_ms` is included and was 0 on each file.

| Case | Decision | Input tokens | Output tokens | cost_usd | duration_ms |
| --- | --- | ---: | ---: | ---: | ---: |
| APP-1001 | approve | 3,644 | 309 | 0.004262 | 56,910 |
| APP-1002 | deny | 3,821 | 400 | 0.004621 | 60,951 |
| APP-1003 | refer | 3,592 | 265 | 0.004122 | 42,328 |
| Batch |  | 11,057 | 974 | 0.013005 | 160,189 |

The batch cost is about one cent. Each application is a fraction of a cent. Latency is what rules out real time. Four sequential local 12B calls took 42 to 61 seconds per file, and the three files together took 160,189 ms. A bind-now response cannot wait that long. The same sequence belongs on an overnight or asynchronous batch.
