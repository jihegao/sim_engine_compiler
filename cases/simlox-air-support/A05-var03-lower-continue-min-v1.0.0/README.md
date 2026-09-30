# A05 lower continuation minimum

This bounded A05.var03 child changes `MissionType.MNOSA` from the accepted prepared-replacement parent's default (`null`, meaning `MNOS=2`) to `1`. A descriptive label also changes. The [frozen contract](contract.json), [builder](build.py), and [exact diff](exact-diff.json) bind the native input to that parent.

In the guarded fixed-seed CLI run, aircraft #0 fails at 9.8829. Aircraft #1 keeps the mission active while distinct aircraft #2 prepares until 10.3829 and attaches. Aircraft #1 then fails at 11.1325; #2 keeps operating while repaired #0 prepares until 11.6325 and attaches. The mission ends at its original hour 12. The report has zero suspended aircraft-hours, seven operating aircraft-hours, `MTMF=1`, and `STMF=0.875`. The [author replay](review/author-mnosa-validation-2026-09-30.json) passes 195 checks; a separate [independent replay](review/independent-mnosa-2026-09-30.json) passes 68.

The [CLI sign-off](cli-scope-signoff-2026-09-30.md) records raw seals, event and report reconciliations, the parent comparison, and limits. Raw files remain under ignored `runs/`. This one-seed observation does not test starting or resuming a suspended mission below `MNOS`, or establish a general failure policy.
