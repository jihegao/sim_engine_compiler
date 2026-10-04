# K06.var01 v0.2.0 — bounded OPI/SXI input merge

This case derives a self-built donor JSON from accepted K02.var01 named input by removing only the `K02-BASE` Station instance that duplicated target `BASE-01` in the sealed v0.1.0 diagnostic. Guarded session-0 SSH imports the derived JSON to `source.sxi`, copies it byte-for-byte to `source.opi`, imports that file into the accepted K01.var04 `target.sxi`, saves `merged.sxi`, then exports, calculates and reports. The source is not an OPUS10-generated file.

The merged JSON retains `BASE-01` once and adds `K02-NAMED` once in its named Station instance. It appends both non-keyed ProblemDescription rows; every other business table matches the accepted parents. Conversion has zero errors, warnings #108/#126, and zero notes. The 333,227-byte SXO is valid. The event log exactly equals both parents, including mission launch at hour 8 and success at hour 11. Numeric report tables and 72 half-hour system/stock bins equal the accepted K01 report; only ProblemDescription differs. Seventeen local raw files and all source pins are sealed under ignored `runs/` and listed in `evidence-index.json`.

This accepts one CLI merge of self-built `.opi` data into a `.sxi` target. It does not establish OPUS10-generated input compatibility, `.opo` point allocation, LORA, phase scenarios, GUI import, cross-engine equivalence, or general K06 behavior.
