# 4700-3 SIMLOX F35 candidate timing

**Measured 2026-09-26. Status: historical timing of an underloaded original candidate.** The original model omitted SIMLOX `FRT`'s ×1,000,000 failure-rate unit conversion, and its one- and 1000-replication result reports were identical except for `NREP`. These measured times remain valid for those exact saved bytes, but they do **not** measure the corrected [F35 workflow candidate](f35-workflow-candidate.md) or a correctly scaled F35 failure workload. The [model mapping](f35-candidate-mapping.md) also has unresolved mission, repair, resource, inventory and output semantics. No `spare_mvp` or Rust speedup can be derived from these timings.

## Model, host and protocol

- Host: `4700-3`, AMD Ryzen 7 4700U, 8 physical/logical cores. Installed SIMLOX executable version `2017.0.0.0`, SHA-256 `FE24C5BFFC0C0641894BB335484CFB83993E3DB2BD60122DDADFEDD39A8C4DB0`.
- Original native model: `C:\Users\user\Documents\Codex\2026-09-26\simlox-f35-model\models\f35-candidate.sxi`, SHA-256 `4A89200E4D05EE78A18CCEE0A00F19D5C273717F6815B67D894EA85FC7B3438A`. It has `NREPS=1`, `RSEED=1`, `SIMPE=1032` hours, and the result-collection settings documented in the [candidate record](f35-candidate.md).
- Single-replication protocol: copy the exact native model to a unique `.sxi` for each run; execute `-silent -threads 1 -log <unique>.log -calc -close`. Run one warmup and five measured repetitions. All six process exits were 0; each log reports 0 input-conversion errors, warnings and notes and a nonempty `.sxo`.
- Batch protocol: change only `Control.NREPS` from 1 to 1000 in the source-derived JSON, then native import and export. Parsed exports differ at **exactly one field**, `NREPS`; `RSEED=1` and `SIMPE=1032` remain. Variant JSON SHA-256 `149BC0001A55FAFE5BF9B5840103307EA181255CF63CBA4D6B961B8BB8FB4CD3`; imported native `.sxi` SHA-256 `16D755C8BDCFD93A8E7B6565926B43DBB6492126D4E2A7A6307611F2A97E670B`. Run `-silent -threads 8 -log <unique>.log -calc -close` with one warmup and three measured repetitions. All four process exits were 0, each log reports 0 conversion errors/warnings/notes and a nonempty `.sxo`.
- Three measured batch `.sxo` files were each exported with SIMLOX `-jsonreport`; the raw reports confirm `ResultSummary.NREP=1000` and the 0–1032-hour period. The reports are byte-identical. The raw export has trailing JSON commas, so the retained raw bytes are parsed only after in-memory comma removal.

`Simulation time` and `Total execution time` come from SIMLOX's log in 0.01-second resolution. `Wall` comes from PowerShell `Stopwatch` around process start and exit; it includes startup and shutdown. Warmups are excluded from medians.

| Workload | Measured simulation times (s) | Median simulation (s) | Median SIMLOX total (s) | Median process wall (s) |
| --- | --- | ---: | ---: | ---: |
| 1 replication, 1 thread | 0.17 / 0.17 / 0.17 / 0.17 / 0.17 | 0.17 | 0.23 | 2.033 |
| 1000 replications, 8 threads | 1.73 / 1.74 / 1.72 | 1.73 | 1.80 | 2.636 |

The batch median is **578 SIMLOX replications per simulation second** (`1000 / 1.73`) for this **underloaded original candidate** and these settings. Using full process wall time instead gives **379 replications per wall second** (`1000 / 2.636`). These are historical SIMLOX-only throughput descriptions; the single- and batch-replication configurations have different thread counts and cannot isolate parallel scaling.

## Result interpretation

After parsing, the saved 1-replication report and a measured 1000-replication report differ only in `ResultSummary.NREP`; every other exported value is identical. This is an observed property of the current candidate and output configuration, not proof that the canonical F35 stochastic workload was exercised. In particular, the [mapping gaps](f35-candidate-mapping.md) remain, so neither the 0.17-second single run nor the 578-replication/s batch rate supports a cross-engine speedup claim. Finish semantic pairing and output-denominator checks before any efficiency comparison with `spare_mvp`.

## Raw evidence

- Windows single-replication directory: `C:\Users\user\Documents\Codex\2026-09-26\simlox-f35-benchmark-20260926-132725`.
- Windows batch directory: `C:\Users\user\Documents\Codex\2026-09-26\simlox-f35-throughput-20260926`.
- Git-ignored local mirror: `data/local/simlox-f35-benchmark/rep1/` and `data/local/simlox-f35-benchmark/rep1000/`. Both contain `timings.json`, native input copies, `.sxo` outputs and per-run logs; the batch mirror also contains the three unmodified raw result reports. SHA-256 of every copied `.sxi` and `.sxo` matches its `timings.json` entry. Scripts and the one-field JSON variant are in `data/local/simlox-f35-benchmark/`.
