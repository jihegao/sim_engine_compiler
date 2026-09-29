# D02.var04 direct CM spanning a scheduled mission: CLI scope sign-off (2026-09-30)

**Decision:** `native_behavior_accepted_cli_scope`, `reusable_published` for one fixed-seed explicit FM-POS-A direct system CM whose turnaround crosses the scheduled hour-20 mission. This is a bounded D02.var04 result, not a general repair or rescheduling rule.

## Parent, source and exact delta

The accepted [D06 explicit position parent](../D06-explicit-position-direct-repair-v1.0.0/cli-scope-signoff-2026-09-30.md) input SHA-256 is `ee7484a32492d1aa6cd90ad961620ecdd3de1244f09b16ba4a96a2978310ce78`. The [D02.var04 child](native-input.json) input SHA-256 is `19aaca9e7b9ae6eab68685e622a254c7c20f44ef671425f047ee7c05dfdad91c`. The [exact parent diff](parent-diff.json), SHA-256 `c0957b1ae259fc50433ec1586d5321e93b6862b7d634710a441543f13130ed4f`, changes only description and `CMLocation.CMT=0.5→15.5` hours for `FM-POS-A` direct system CM at `BASE-01`. The other 33 parent tables are unchanged, including FailureMode.OPID=`OPHOURS`, FRQ=300000 per million operating hours, seed 1, profile launches at 8/20/32 and 36-hour horizon. The [contract](contract.json) predeclared the cross-mission test.

The installed SIMLOX 2017 manual SHA-256 is `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`; dictionary SHA-256 is `11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0`. The dictionary defines CMLocation.CMT as nonnegative corrective-maintenance turnaround in hours. Neither proprietary source is uploaded.

## Native run and observed comparison

Run ID `d02-var04-cross-cm-v100-ssh-20260930-01` used session-0 SSH, the `Global\SimloxIssue18NativeQueue` host-wide mutex and GUI PID 13340 identity guard. Import, export, calculation, report and roundtrip checker all completed at exit code zero. All **18 row-containing source tables** roundtripped exactly, including all-null placeholder rows. Conversion had **zero errors and one warning**, #108 for logging.

The accepted D06 parent and child both log the first FM-POS-A critical failure at 9.8829 during the 8–10 mission. In the child, that mission aborts; direct system CM starts at 10, performs a no-resource subtask planned for 15.5 hours, and completes at 25.5. The second mission is ordered and activated at 19 while the aircraft is in repair, waits for a system until its 20.3333 timeout, and cancels. The aircraft returns ready at 25.5. The third mission starts at 32 and succeeds at 34. The shorter-CM D06 parent instead succeeds on its hour-20 mission and has a second failure/repair at 33.8602/34–34.5. Different later failure draws are observed; they are not treated as evidence of equivalent random streams.

The 72 half-hour child `SystemResults` bins cover 0–36. They show one failure in 9.5–10, one completed repair in 25.5–26, and `NSYRP=1` for exactly 31 bins from 10–25.5: **15.5 aircraft-hours in repair**. No mission operation is reported during 20–22. The stock report has no demand or backorder, and one aircraft is ready at the hour-36 stop. The report's mission success fraction is 1/3, consistent with one aborted, one cancelled and one successful mission; the cancellation itself is established by the event log, as `SystemResults` has no separate cancellation metric. This case does not infer labor occupancy from the CMT duration.

| Child raw artifact | SHA-256 |
| --- | --- |
| `invocation.json` | `a0a314ac77439830486a40cfab837c3ac7aabea13d5d36d348fcb5836452093d` |
| `closure.json` | `b5631b5203dd9bbeb6f13175b400787ad8d2c8282b6fc9afdf4104b53f1696e1` |
| `model.log` | `0a28362f09d7659c22086615db8d1d29faec9485f712540467f0a97337e8f81e` |
| `report-raw.json` | `df3feab359cd60659178a95ca7988a67cce5839cc726d412f37d8a767984efea` |

The [author validator](validate_cross_mission.py), SHA-256 `248618fac073841b53ae54c4998ae44b629c1ac5808334db4001d33c515522d9`, passes [62/62 checks](review/author-cross-validation-2026-09-30.json), SHA-256 `3e266abb6e586696f21d813ea351c7831025c2b1df46fb21b70c690492ad9ce8`.

A separate reviewer wrote a [read-only replay](review/independent_cross_cm_readonly.py), SHA-256 `df9ac9014497b4642d25c2227d1b07b9fc68f6a1189d875b9c82a9e2ec03b111`, without importing the author validator. Its [94/94 result](review/independent-cross-cm-2026-09-30.json), SHA-256 `fbb5d00d9830d6ff29d7ec1c15b29d9fbc56a9d0e84c5decdf1a5a8f425e39ba`, independently verifies exact source/diff and raw seals, the guarded invocation, conversion and roundtrip, the D06 control, event timeline and aligned report bins.

This result is specific to installed SIMLOX executable SHA-256 `fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0`, one explicit FMID and one fixed seed. It does not test alternative positions, replacement, resource capacity, other mission timeouts, GUI visual content or cross-engine equivalence. Issue #18 stays open.
