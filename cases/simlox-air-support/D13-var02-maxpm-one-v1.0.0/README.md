# D13.var02 MAXPM=1 control, v1.0.0

This input derives from [accepted D03](../D03-calendar-pm-v1.0.0/cli-scope-signoff-2026-09-30.md). It deploys two identical aircraft at one unit, sets `Unit.MAXPM=1`, and gives their `CALHOURS=24` PM tasks a noncritical window with `ATIM=0`, `DTIM=0.5`. The [parent diff](parent-diff.json) records the exact six-table change, including the shorter 36-hour observation window. Each PM subtask is a fixed one hour and requires no resource.

The two PM task objects are both marked started at hour 24, but the performed subtasks run 24–25 and 25–26. The paired [D13.var02 sign-off](../D13-var02-maxpm-two-v1.0.0/cli-scope-signoff-2026-09-30.md) compares this frozen input with the otherwise identical `MAXPM=2` control. `python build.py` verifies [this input](native-input.json). The [SSH runner](run_native_ssh.ps1) writes raw native evidence under ignored local `runs/` and guards the live GUI and host-wide native queue.
