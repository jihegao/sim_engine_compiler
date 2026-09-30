# A06 extendable mission after prepared replacements

This bounded A06 child derives from the accepted [A05 prepared-replacement parent](../A05-var02-prepared-spare-probe-v1.0.0/cli-scope-signoff-2026-09-30.md). It changes only `MissionType.MPAT=CONTINUOUS→EXTENDABLE` and a descriptive label. The [frozen contract](contract.json), [builder](build.py), and [exact diff](exact-diff.json) bind the source to that parent.

The guarded fixed-seed native run starts a two-aircraft mission at hour 8. Aircraft #0 fails at 9.8829, causing suspension until prepared #2 attaches at 10.3829. Aircraft #1 then fails at 12.2431, causing a second suspension until repaired #0 prepares and attaches at 12.7431. The mission completes at hour 13 after four active hours across five calendar hours. The 32-bin report integrates eight aircraft operation hours and one suspended aircraft-hour. The [author replay](review/author-extendable-validation-2026-09-30.json) passes 198 checks; a separate [independent replay](review/independent-extendable-2026-09-30.json) passes 72.

Raw native files remain in ignored `runs/`; the sign-off gives their hashes and bounded acceptance. One fixed seed does not establish generic interruption behavior, a deterministic unavailable interval, or the separate no-interruption and horizon boundaries.
