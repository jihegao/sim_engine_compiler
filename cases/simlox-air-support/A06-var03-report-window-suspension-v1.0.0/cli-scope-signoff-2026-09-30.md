# A06.var03 suspension crossing a result-window end: CLI scope sign-off (2026-09-30)

**Decision:** `native_behavior_accepted_cli_scope`, `reusable_published` for one fixed-seed extendable mission that suspends across a 12.5-hour result-window end while its simulation continues to hour 16. The event log records later resumption and completion at 12.7431 and 13; the time-series result bins end at 12.5. Full-simulation summary measures and time-limited report-bin totals are explicitly separate.

## Source and exact delta

The accepted [A06 extendable parent](../A06-extendable-prepared-gap-v1.0.0/cli-scope-signoff-2026-09-30.md) input SHA-256 is `5b53aa2cbaacb283e15bb7e7852afba215ec7fe5961434c3c2ce6f06768125c7`. The [child input](native-input.json) SHA-256 is `0fcd389734758af9b0c5c1b5ae4adfbca27135153954384b2cf7333ac4c9b3ff`. The [exact diff](exact-diff.json) SHA-256 is `87026198ef5c3fe6170de5ee785c3d25bc4a7c93cdb53317ef2f8ca0365dd6a5`: `Control.RCEND` and both `ResultCollection.RCEND` rows change 16→12.5 hours while `Control.SIMPE` stays 16; `ProblemDescription.PDESC` changes a label. The other 28 tables, aircraft, `MPAT=EXTENDABLE`, `DURN=4`, two-aircraft minimum, preparation, failure/repair, seed and schedule stay unchanged. The [contract](contract.json) SHA-256 `6ca625ff8581e352464d233f81deba2d0fe1d6723e14704067cf3bb11da0a5b4` predeclared the comparison before native execution.

The installed SIMLOX 2017 manual SHA-256 is `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`. Physical PDF pages 179, 182–183 and 265–266 describe extendable suspension and completion. Physical page 645 defines `SYDT` as mean completed system downtime and `NSYDT` as its period count; completed periods are registered in the interval where downtime started, while periods unfinished at simulation end are excluded. The installed dictionary SHA-256 is `11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0`. Neither proprietary file is uploaded.

## Sealed native result

Run `a06-var03-report-window-v100-ssh-20260930-01` used session-0 SSH with an `sshd.exe` ancestor, the host-wide `Global\SimloxIssue18NativeQueue` mutex, and GUI PID 13340/session-1 identity guard. Import, export, calculation, report and exact source roundtrip checker exited zero. All 16 row-containing source business tables roundtripped exactly. Conversion errors were zero; warning #108 enables event logging and #126 denotes the teaching aircraft with no items. The native JSON writer's trailing commas are normalized only in a parser copy; raw bytes and hashes are retained.

| Raw artifact | SHA-256 |
| --- | --- |
| `invocation.json` | `cb22f723fb5945ab3bb3af4286c9c662cfdd11e26ec3839fbd4d100519d6b9b2` |
| `closure.json` | `e356ab82674d50d2afce6a5c192eae97b756f34b7529e2b081c06332f420923a` |
| `model.log` | `55164fba5af8523e77679b49462a7ea45cb3655694891c1935a0d7c4c0384fae` |
| `report-raw.json` | `c8ebd9d2bf07f3d265727a69e9b6ccea148ff5dfb9dd5a668bdf2663ce0fde47` |

The child `model.log` SHA-256 equals the accepted full A06 parent's log SHA-256 exactly. Aircraft #0/#1 start at hour 8. #0 fails and the mission suspends at **9.8829**; prepared #2 attaches and it resumes at **10.3829**. #1 fails and the mission suspends again at **12.2431**, leaving #2 attached while repaired #0 starts preparation and #1 starts direct repair. The result window ends at **12.5** within that second suspension. The simulation then continues: #0's preparation and #1's repair complete at **12.7431**, #0 attaches, the mission resumes, and #2/#0 complete it at **13**. These later events are supported by the log, not by post-window time-series bins.

The 25 aligned half-hour `SystemResults` and `StockTotalResults` bins cover 0–12.5. They integrate **7.4862882495 aircraft mission-hours** (`NSYMO=STACC`), **0.7568558604 suspended aircraft-hour** (`NSYMS`), **0.7568558604 repair aircraft-hour** (`NSYRP`), and **1.7568558604 preparation aircraft-hours** (`NSYMP`). Their event counts are two failures, one repair completion, four preparation starts and three completions; stock demand/backorder remain zero. These interval totals match the accepted [A06.var04 simulation-stop control](../A06-var04-horizon-suspension-v1.0.0/cli-scope-signoff-2026-09-30.md). The final system bin differs only at `SYDT=0.5,NSYDT=1` versus `null,0` in the stopped control: repair completion beyond 12.5 registers the completed half-hour downtime in its earlier 12–12.5 start interval. The final bin is an interval result, not an instantaneous terminal inventory.

In contrast, `ResultSummary.RTIUP=16` and `MTMF=STMF=1` reflect the full simulation. They do not describe only the 0–12.5 bins. The ≈0.256856 active hour still outstanding at the report end is inferred from `DURN` and the 7.486288 aircraft-hours divided by two; it is not a native remaining-work field. The later hour-13 completion is directly logged.

The [author validator](validate_window.py), SHA-256 `15b0e74460a8657170e22ab97e34bbebf4b909cdaebaab5f3d5298a48112886`, passes [171/171 checks](review/author-window-validation-2026-09-30.json), SHA-256 `b724b014b83a59f4632f697dc7a107950941f800fa6ff36c2ab1cfddf9993cc9`. A separate [independent read-only replay](review/independent_window_readonly.py), SHA-256 `c118c181fa0279b30ce297b4d5ff3ce78310dfea208fa05dda6a5423555064ab`, passes [67/67 checks](review/independent-window-2026-09-30.json), SHA-256 `d2d443972449e67b4a33c0fbc5630b3858c9332b39588b4c81ecd4b86dd11040`, without importing the author validator. Raw native files remain in ignored local `runs/`.

This evidence is specific to installed SIMLOX executable SHA-256 `fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0`, one seed and observed stochastic failure times. The 12.5 result end was selected from the accepted event timeline, not from a deterministic unavailable interval. Other report windows, GUI visual content and cross-engine equivalence remain unverified. Issue #18 stays open.
