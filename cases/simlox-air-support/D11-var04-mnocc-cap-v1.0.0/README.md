# D11.var04 MNOCC direct occurrence cap

This fixed-seed CLI case group derives from the accepted [D10.var02 three-counter PM](../D10-var02-multi-counter-v1.0.0/README.md). It keeps one aircraft, five fixed missions, one `MS2` preventive task, and three interval counters. The three source branches set only `MaterielPM.MNOCC` to 0, 1, or 2, plus a descriptive label.

The [pre-run contract](contract.json) froze the hypothesis that the 0 branch would perform no PM, the 1 branch would work at 12–13, and the 2 branch would work at 12–13 and 21–22. `build.py` replays all three frozen inputs and `describe_diff.py` checks parent and pairwise deltas. The guarded `run_native_ssh.ps1` runner requires session-0 SSH, the host-wide Issue #18 queue, source SHA-256 pins, and preservation of the existing GUI process. Raw runs remain local under ignored `runs/`. `check_roundtrip.py` checks source import/export identity; `validate_native.py` replays source-bound raw evidence.

The manual defines MNOCC as the maximum remaining occurrences from simulation start and says that related PM can also consume the count. This package tests only a direct cap on one PM task. A separate related-PM model is required to assess that interaction. Native observations are not publication-ready until independent review and the CLI scope signoff are complete.
