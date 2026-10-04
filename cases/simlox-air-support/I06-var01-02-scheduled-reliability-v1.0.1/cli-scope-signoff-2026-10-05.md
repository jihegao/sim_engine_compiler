# I06.var01–02 scheduled reliability — bounded CLI signoff

**Decision: GO for this fixed-seed CLI scope.** The v1.0.1 [contract](contract.json) was frozen before execution and its gates passed. This signoff covers 12 paired inputs: traditional primary LRU OPHOURS `FRTCF` and explicit position-A failure-mode CALHOURS `FRQCF`, each at seeds 1–3 with factor-1 control versus factor-4 intervention at h9. Every arm sets factor 1 at h24. The item mission runs h23–25 so the h24 reset occurs during operating exposure in the seed-1 pair.

The inputs derive from accepted D02.var01 and D02.var02 parents pinned by SHA-256 in the contract. Within a seed pair, only the h9 factor and description change. All six failure-mode inputs are byte-identical to v1.0.0; all six v1.0.1 item inputs change only the third mission start h52→23 from that excluded diagnostic. Initial rates, clocks, stock, repair, collection and horizon are fixed within pairs. The installed SIMLOX 2017 manual, SHA-256 `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`, physical pp. 494–497, specifies positive FRTCF/FRQCF factors keyed by item or failure mode and TIMEC.

The session-0 SSH run `i06-var01-02-reliability-panel-v101-ssh-20261005-01` completed all **48/48** serial native import, export, calculation and report steps under the host mutex, targeted watchdog and protected GUI PID 13340/session 1 check. The [closure](evidence-index.json) records SHA-256 for **122 local raw files** and equal source hashes before/after; raw files are retained locally outside Git. All arms reported converter errors 0, Warning #108 only and notes 0. Twelve native exported inputs roundtrip all authored populated column names, types and cell values across 19 populated tables each. The exporter adds `key:true` column metadata, so the exported JSON is not byte-identical to the authored source. Each default report has one trailing comma before the table array closes; both validators remove that single comma for parsing while retaining and sealing the raw report.

The native event logs show next-failure recomputation at h9 and h24 for both kinds; the accepted D02 parents do not have the h24 change event. In the item seed-1 pair, the h24 recomputation is finite while the h23–25 mission remains active: control next failure h26.4666, intervention h34.4659. The h9 schedules also differ. The physical failure counts inside the h9–24 factor window are:

| Kind | Seed | Control | Factor 4 |
| --- | ---: | ---: | ---: |
| Traditional item | 1 | 0 | 2 |
| Traditional item | 2 | 2 | 1 |
| Traditional item | 3 | 0 | 2 |
| Position failure mode | 1 | 1 | 8 |
| Position failure mode | 2 | 1 | 8 |
| Position failure mode | 3 | 7 | 12 |

All 12 arms are retained, including seed pairs where the finite schedule or outcomes differ from an intuitive monotone ordering. The author [validator](review/author-validation-2026-10-05.json) passed **306/306** checks. The separately written [independent replay](review/independent-verdict.json) passed **2704/2704**, including raw seals, 48 guarded steps, exact populated-cell roundtrips, h9/h24 schedule witnesses, physical failures and repairs, report bins, mission successes/aborts/cancellations and terminal readiness. The failure-mode seed-2 control terminal half-hour readiness average is approximately 0.02498; it is not rounded to 1. The independent verdict is **GO_BOUNDED**.

The [v1.0.0 diagnostic](../I06-var01-02-scheduled-reliability-v1.0.0/README.md), closure SHA-256 `a127c7ede30bff5f62411ed419f85b5b235b8e2d9e8d0347109e27dbc1f5d9b2`, passed 2435/2437 replay checks but failed its frozen h24 exposure gate. It is excluded from this publication and has no publication-index entry.

**Limits.** The log does not print the applied numeric factor; its value and interpretation come from frozen source and the pinned manual. Native evidence establishes timed rescheduling and these fixed-seed outcomes, not a multiplier inferred from event counts, a general factor law or a population probability. Scope is one traditional primary LRU, one explicit position failure mode, two clocks, three seeds per kind and one h9–24 intervention window. Other targets, boundary values, clocks, GUI presentation, cross-engine behavior and full I06/Issue #18 remain unverified.
