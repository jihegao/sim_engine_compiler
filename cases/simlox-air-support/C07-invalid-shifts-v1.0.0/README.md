# C07.var05: overlapping shifts and capacity above nominal

This bounded candidate changes one business field at a time from the accepted [C07.var04 explicit or repeated input](../C07-repeat-nested-v1.0.0/README.md). The [pre-run contract](contract.json) and [exact diff](exact-diff.json) freeze the two accepted parents and three child inputs. The installed manual, SHA-256 `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`, describes shift rows on physical pages 419–421, overlap errors #249/#250 on page 799, and capacity warning #60 on page 843.

| Input | Only business-field change | Native result |
| --- | --- | --- |
| `overlap-input.json` | Second explicit `ShiftProfile.STIM` 26 → 24.5, overlapping the 23–25 window | Error #250, one conversion error, unusable four-byte `.sxo` |
| `repeated-overlap-input.json` | Repeated `ShiftProfile.IINT` 3 → 1.5, shorter than its two-hour window | Errors #249 and #250, two conversion errors, unusable four-byte `.sxo` |
| `over-capacity-input.json` | `ShiftResource.QTY` 2 → 3 while nominal deployment `ResourceAllocation.RQTY` remains 2 | Warning #60, zero conversion errors, valid two-crew outcome |

Only `ProblemDescription` also changes, to label each input. Guarded, serial session-0 SSH native runs completed import, export, calculation and source roundtrip for all three; the capacity run also completed JSON reporting. The host-wide Issue #18 mutex and GUI PID 13340/session 1 were guarded. All 24 row-containing source tables roundtrip exactly for each run. Warnings #108/#126 accompany all three; warning #60 occurs only in the capacity run. The overlap calculation commands exit zero despite converter rejection, so the diagnostics and unusable `.sxo` establish the negative outcome. Their runner did not call `jsonreport`.

The capacity input preserves QTY 3 through native import/export. Its `model.log` is byte-identical to the accepted explicit QTY 2 control, and its parsed native report tables differ only in `ProblemDescription`. The 72 half-hour bins show effective resource capacity two, four crew-hours worked, two resource-hours of waiting demand, successful 28–29 formation and two aircraft ready at the horizon. The [author replay](validate_native.py) and separate [independent read-only replay](review/independent_readonly.py) verify the frozen source deltas, run seals, roundtrips, diagnostics, outcome and report ledgers. The independent replay passes 184/184 checks. Original native artifacts remain locally under ignored `runs/`; the [evidence index](evidence-index.json) records their paths and hashes without publishing raw files.

This establishes one explicit overlap rejection, one repeated-interval overlap rejection, and one warning/clamp against nominal two-crew deployment on the installed executable. It does not establish general invalid-shift handling, multiple-resource clamping, calendar recurrence, `MAXUT`, GUI visual behavior or cross-engine equivalence. Other C07 variants, C08 and Issue #18 remain open.

For a fresh native run, use `build.py` and `describe_diff.py` to recreate and compare inputs, then run `run_rejection_ssh.ps1 -Variant overlap|repeated-overlap -RunId <fresh-id>` or `run_capacity_ssh.ps1 -Variant over-capacity -RunId <fresh-id>` through guarded session-0 SSH. Update replay run IDs only for newly sealed runs.
