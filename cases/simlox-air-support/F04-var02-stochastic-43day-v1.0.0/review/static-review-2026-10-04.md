# Independent F04.var02 review (2026-10-04)

## Frozen pre-run review

**GO for two serial guarded native runs.** Accepted F04.var01 input/closure/sign-off, the excluded one-rep and 32-rep pilot evidence, candidate input, diff, contract, and OUTRP selector matched their frozen SHA-256 pins. The parent-to-candidate delta was exactly seven cells (description, NREPS 1→128, TCLEV null→0, System/LRU/SRU FRT 0→1,000,000, RISK mission MFF 0→1) plus two `ReplicationResultControlSystem` rows with `TOTAL=Y`, `TIME=N`, `SNAPS=N`. Relative to the 32-rep pilot, only description and NREPS changed. The selector differed from installed Default.sxs by one `N→Y` byte at offset 67165.

PowerShell and Python parsed cleanly. The runner required session-0 SSH with an `sshd.exe` ancestor, the host mutex, an active GUI PID 13340, hidden CLI execution, source seals before and after, exact converter `Errors: 0, Warnings: 1 (#108), Notes: 0`, import/export checking, and a sealed closure. The contract froze nominal two-sided 95% Student-t half-width targets of 0.05 absolute for mission success, 5% relative for flight hours, and 10% relative for observed failures. Preflight GO did not establish those outcomes.

## Independent post-run replay

**GO_BOUNDED: 13,832/13,832 independent checks passed.** The self-contained [replay](independent_replay.py) reads frozen sources and raw run artifacts without importing author validation; its only write is [verdict JSON](independent-verdict.json). Both native closures are clean and seal all 14 raw files each. Each run has 128 distinct replication IDs and 256 System TOTAL rows, one for each replication and each of two units. The first-replication log has 63 mission starts, 43 successes, 20 aborts, and 27 critical random failures; it is byte-identical to the sealed 32-rep pilot log. The per-replication means reconcile with ResultSummary and aggregate SystemResults bins. Same-seed event log and both report files are byte-identical across the two runs.

| Metric | Mean | Nominal t95 half-width | Frozen limit |
| --- | ---: | ---: | ---: |
| Mission success fraction | 0.6724950592 | 0.0017720712 | 0.05 absolute |
| Aircraft flight hours | 158.8066821 | 0.9298680 | 7.9403341 (5%) |
| Observed failures | 25.90625 | 0.4031912 | 2.590625 (10%) |

The default native report has one trailing comma before its final table-array bracket; the replay preserves raw bytes and removes only that comma for parsing. The separate OUTRP report parses as strict JSON. Native `ResultSummary.RSM*` values differ from empirical sample standard errors, so the intervals use the 128 per-replication values directly. Repeating the same input and seed establishes execution repeatability, not 256 independent draws. Only first-replication events are visible in ENLOG; stock and resource figures are descriptive aggregates. The result is confined to this installed CLI engine, model, and configured pseudo-random stream.

Replay source SHA-256: `c683e305e0f65929d96633784eaa39a9e76eef3087914072d7601ac382c32518`
Verdict JSON SHA-256: `dfba87aa2fb076a3ca511ddba882243e334988f000a4816979f8a054d8bfd74f`
