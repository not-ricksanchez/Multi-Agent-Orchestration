# Cost and latency

These figures come from `summarize_trace` on the three files written by `scripts/run_three_cases.py` against `qwen3:8b` with `think` false, run `20261011T231927Z-aa3f6c` (`traces/20261011T231927Z-aa3f6c/`). Each run writes to its own `traces/<run_id>/` directory, so a re-run never mixes spans into an earlier run's files. The script does not overwrite the model's decision.

The dollar amounts are faked. `qwen3:8b` ran locally through Ollama, which does not bill per token. The formula below is used to **mock** the cost here, used only to show what the same token counts would cost if this pipeline called a paid model.

Price formula, stored on every model span:

```text
cost_usd = (input_tokens * 1 + output_tokens * 2) / 1_000_000
```

That is $1 per million input tokens and $2 per million output tokens. The bureau lookup is not a model call, so it is omitted from this table. Its duration was 0 ms on each file.

Per agent:


| Case     | Agent           | Input tokens | Output tokens | duration_ms | duration_s | cost_usd |
| -------- | --------------- | ------------ | ------------- | ----------- | ---------- | -------- |
| APP-1001 | intake          | 668          | 94            | 6,235       | 6.2        | 0.000856 |
| APP-1001 | enrichment      | 1,314        | 79            | 5,037       | 5.0        | 0.001472 |
| APP-1001 | risk            | 701          | 32            | 3,856       | 3.9        | 0.000765 |
| APP-1001 | recommendation  | 583          | 80            | 6,507       | 6.5        | 0.000743 |
| APP-1001 | total (approve) | 3,266        | 285           | 21,635      | 21.6       | 0.003836 |
| APP-1002 | intake          | 666          | 92            | 6,000       | 6.0        | 0.000850 |
| APP-1002 | enrichment      | 1,431        | 89            | 6,714       | 6.7        | 0.001609 |
| APP-1002 | risk            | 709          | 65            | 4,616       | 4.6        | 0.000839 |
| APP-1002 | recommendation  | 624          | 64            | 4,610       | 4.6        | 0.000752 |
| APP-1002 | total (deny)    | 3,430        | 310           | 21,940      | 21.9       | 0.004050 |
| APP-1003 | intake          | 659          | 96            | 6,440       | 6.4        | 0.000851 |
| APP-1003 | enrichment      | 1,310        | 54            | 4,197       | 4.2        | 0.001418 |
| APP-1003 | risk            | 684          | 33            | 2,788       | 2.8        | 0.000750 |
| APP-1003 | recommendation  | 567          | 46            | 3,589       | 3.6        | 0.000659 |
| APP-1003 | total (refer)   | 3,220        | 229           | 17,014      | 17.0       | 0.003678 |
| Batch    |                 | 9,916        | 824           | 60,589      | 60.6       | 0.011564 |


The batch cost at that assumed rate is about one cent. Each application is a fraction of a cent. Latency is still what rules out real time. Four sequential local 8B calls with thinking off took 17 to 22 seconds per file, and the three files together took 60,589 ms. That is about 2.5× faster than the earlier `gemma3:12b` batch (160,189 ms), but a bind-now response still cannot wait ~20 s. The same sequence belongs on an overnight or asynchronous batch.