# D05.var01 worker capacity comparison: CLI scope sign-off (2026-09-30)

**Decision:** `native_behavior_accepted_cli_scope`, `reusable_published` for a fixed, paired one-versus-two-worker comparison. The parent [D05 one-worker release](../D05-maintenance-competition-v1.0.0/cli-scope-signoff-2026-09-30.md) is already accepted; this package adds the two-worker control. It does not accept all D05.var01 capacity boundaries.

## Source, execution, and raw evidence

The accepted parent input SHA-256 is `4443d057ade36010a84186aa0f9ac8279886563db190ed80699b7fe48ad2baad`; the [two-worker input](native-input.json) SHA-256 is `a29857331ed02bf4150c04be71d34a5f84ce66e6e76f1db27bdd94a14320686a`. The [exact parent diff](parent-diff.json), SHA-256 `db7af19ab98871ce762cb6362d44f72ab2827badb70dd94ddba0dd1b082895b0`, changes only three tables: `ResourceAllocation.RQTY=1→2` is the sole behavioral change, and two descriptive labels change. System failure rate, seed, mission/PM/repair tasks, `Unit.MAXPM=2`, horizons, and resource demand per subtask remain identical. The [contract](contract.json) states the comparison bounds.

Native run ID `d05-var01-two-v100-ssh-20260930-01` used session-0 SSH, the host-wide `Global\SimloxIssue18NativeQueue` mutex, and active GUI PID 13340 identity guard. Import, export, calculation, JSON report and roundtrip checker exited zero; all 22 source row-containing tables roundtripped exactly. As with the parent, three are all-null source placeholder rows; native export adds nine all-null placeholder tables. Conversion had zero errors and the documented #108 logging and #126 item-free warnings. Raw outputs remain in the local ignored `runs/` directory.

| Two-worker raw artifact | SHA-256 |
| --- | --- |
| `invocation.json` | `6e650d74900f7925df32cb09b1ab6ce7c0e22913166f09bee1fd6ab00365fc8d` |
| `closure.json` | `3644344aced44e9563aac10262f877d1af6ea68a06213019f8cd3d3110ee770a` |
| `model.log` | `c4584d4eac4062626d87a38428c4297266f22d0539ecb9c54d978e5142bcc46a` |
| `report-raw.json` | `360a4156232cb4c8b907f40f9786b05e5aeea202b8743c8aaf76ea9c0914eb3b` |

## Matched behavior and capacity effect

Both runs launch missions at 8, 20 and 32 hours. The first succeeds at 10; the same aircraft 1 critical failure at 22.6835 aborts the second mission; the third succeeds at 34. The failed aircraft returns at 23, and its direct repair holds one worker 23–28. Both aircraft receive PM task-object start markers at hour 24. These markers do not show physical PM work.

| Worker quantity | Repair work | Healthy aircraft PM work | Failed aircraft PM work | Peak workers used | Worker-hours used / waiting |
| --- | --- | --- | --- | --- | --- |
| 1, accepted parent | 23–28 | 28–29 | 29–30 | 1 | 7 / 5 |
| 2, this control | 23–28 | **24–25, overlapping repair** | 28–29 | 2 | 7 / 0 |

With two workers, the event log books one at 23, a second at 24, releases one at 25, releases the repair worker at 28, immediately books one for the failed aircraft's PM, and releases it at 29. The ledger never exceeds two and ends with both free. The failed aircraft's PM remains blocked by its **own critical repair** until 28, even though spare worker capacity exists from 25–28; its task object was already marked started at 24. The 72 half-hour report bins in each run preserve one failure/repair and two PM starts/completions. Both have five repair aircraft-hours, two PM aircraft-hours, seven worker-use hours, two ready aircraft at 36, and mission success 2/3. Resource wait changes from five to zero worker-hours. The unchanged fault and mission timeline makes the staffing delta interpretable in this fixed seed, not a general claim about random-stream invariance under arbitrary edits.

## Replay and limits

The [author pair replay](review/author-pair-validation-2026-09-30.json) passed **113/113** checks, SHA-256 `5fd02b635658a96376bdbdc5d01b80a61324e64d4c98ed9570a4381ac29529d`; its [validator](validate_pair.py) SHA-256 is `5500554ffa0e4e00f60c184f3ac0c8f3cb45ae1a855eb12c5b050fd7570a521d`. A separate reviewer wrote a [standard-library-only read-only pair replay](review/independent_pair_readonly.py), SHA-256 `8e2f4b82dc94e8b7562eccf867b488ca591742b93263f7058cec912011184bc9`, without importing author code. Its [63/63 result](review/independent-pair-2026-09-30.json), SHA-256 `1917c46914aa75333584a3ee7aa2aeb2e9be554271f1c58262978af7cd393b8e`, agrees with the source, native events and resource ledger.

This release tests resource quantity 1 versus 2 only, with one fixed-seed critical direct failure and noncritical calendar PM. It does not establish zero-worker handling, other fault draws, critical PM ordering, noncritical failure ordering, same-time event priority, mission cancellation due to maintenance wait, later PM cycles, GUI visual content, or cross-engine equivalence. GUI identity was guarded but its visual content was not sampled. Issue #18 remains open.
