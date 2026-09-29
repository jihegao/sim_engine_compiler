# D04 operation-hour preventive maintenance, v1.0.0

This bounded case derives from [accepted D03](../D03-calendar-pm-v1.0.0/cli-scope-signoff-2026-09-30.md). It keeps the same generic aircraft and fixed one-hour PM task, but uses a three-`OPHOURS` threshold. A two-hour mission runs 8–10, followed by a 30-hour no-flight gap and a one-hour mission 40–41. The aircraft is notified and reserved from hour 39 for the second mission, so the gap is a **no-flight interval**, not continuous ready time.

The [parent diff](parent-diff.json) lists the exact changed tables. The [CLI scope sign-off](cli-scope-signoff-2026-09-30.md) accepts one PM at 41–42 after the second mission returns and no PM during the long no-flight gap. This single threshold-crossing run does not establish behavior for mission conflict, multiple PM cycles, `ATIM/DTIM` tolerance, other operation parameters, or resources.

Run `python build.py` to verify the frozen [input](native-input.json). The [SSH runner](run_native_ssh.ps1) requires session 0, the host-wide Issue #18 queue, the expected live GUI identity, and SHA-locked source. Native outputs stay under ignored local `runs/`; the retained [author replay](review/author-native-validation-2026-09-30.json) and [independent review](review/independent-native-review-2026-09-30.json) can be inspected without rerunning SIMLOX.
