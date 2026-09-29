# D13.var02 MAXPM=2 control, v1.0.0

This input derives from the frozen [MAXPM=1 control](../D13-var02-maxpm-one-v1.0.0/README.md). The [parent diff](parent-diff.json) changes only `Unit.MAXPM=1→2` and a descriptive label. Both aircraft reach the same noncritical calendar PM boundary at hour 24. With `MAXPM=2`, their one-hour subtasks perform together from 24–25, compared with serial 24–26 performance at `MAXPM=1`.

The [paired CLI sign-off](cli-scope-signoff-2026-09-30.md) records the exact bounded behavior, hashes, and limits. Run `python build.py` to verify [this input](native-input.json). The [pair validator](validate_pair.py) reads both ignored local native runs without invoking SIMLOX. The [author replay](review/author-pair-validation-2026-09-30.json) and [independent review](review/independent-pair-review-2026-09-30.json) are retained in the repository.
