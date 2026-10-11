# Cost and latency

These figures come from `summarize_trace` on the three files written by `scripts/run_three_cases.py` against `gemma3:12b`, run `20261011T211553Z-78777c` (`traces/20261011T211553Z-78777c/`). Each run writes to its own `traces/<run_id>/` directory, so a re-run never mixes spans into an earlier run's files. The script does not overwrite the model's decision.

The dollar amounts are faked. `gemma3:12b` ran locally through Ollama, which does not bill per token. The formula below is an assumed hosted-API price, used only to show what the same token counts would cost if this pipeline called a paid model.

Price formula, stored on every model span:

```text
cost_usd = (input_tokens * 1 + output_tokens * 2) / 1_000_000
```

That is $1 per million input tokens and $2 per million output tokens. The bureau lookup is not a model call, so it is omitted from this table. Its duration was 0 ms on each file.

Per agent:

| Case | Agent | Input tokens | Output tokens | duration_ms | duration_s | cost_usd |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| APP-1001 | intake | 759 | 109 | 22,253 | 22.3 | 0.000977 |
| APP-1001 | enrichment | 1,500 | 94 | 16,757 | 16.8 | 0.001688 |
| APP-1001 | risk | 750 | 50 | 9,068 | 9.1 | 0.000850 |
| APP-1001 | recommendation | 635 | 56 | 8,832 | 8.8 | 0.000747 |
| APP-1001 | total (approve) | 3,644 | 309 | 56,910 | 56.9 | 0.004262 |
| APP-1002 | intake | 758 | 108 | 14,591 | 14.6 | 0.000974 |
| APP-1002 | enrichment | 1,620 | 113 | 18,613 | 18.6 | 0.001846 |
| APP-1002 | risk | 760 | 100 | 15,192 | 15.2 | 0.000960 |
| APP-1002 | recommendation | 683 | 79 | 12,555 | 12.6 | 0.000841 |
| APP-1002 | total (deny) | 3,821 | 400 | 60,951 | 61.0 | 0.004621 |
| APP-1003 | intake | 751 | 112 | 15,609 | 15.6 | 0.000975 |
| APP-1003 | enrichment | 1,496 | 65 | 10,361 | 10.4 | 0.001626 |
| APP-1003 | risk | 732 | 44 | 9,001 | 9.0 | 0.000820 |
| APP-1003 | recommendation | 613 | 44 | 7,357 | 7.4 | 0.000701 |
| APP-1003 | total (refer) | 3,592 | 265 | 42,328 | 42.3 | 0.004122 |
| Batch |  | 11,057 | 974 | 160,189 | 160.2 | 0.013005 |

The batch cost at that assumed rate is about one cent. Each application is a fraction of a cent. Latency is what rules out real time. Four sequential local 12B calls took 42 to 61 seconds per file, and the three files together took 160,189 ms. Enrichment was the slowest model step on every file (10–19 s) because its prompt is the longest; recommendation was the cheapest. A bind-now response cannot wait that long. The same sequence belongs on an overnight or asynchronous batch.
