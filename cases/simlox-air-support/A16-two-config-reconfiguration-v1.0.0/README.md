# A16: two configuration changes and return to base

This fixed-seed native model starts with one `TEACH-AIR-01` aircraft. `CBSID` configurations A and B each add one LRU. Three scheduled missions require A, then B, then the base type at hours 8, 20 and 32. The accepted E01 task breakdown supplies explicit ten-minute `<REMOVE>` and twenty-minute `<REPLACE>` work. One spare of each configuration LRU starts at the base.

`build.py` verifies the frozen input derived from the accepted E01 parent and A11 `MissionSystem` schema. `describe_diff.py` verifies the exact parent delta. The guarded `run_native_ssh.ps1` generated one immutable native run under ignored `runs/`. `validate_native.py` and the separate `review/independent_readonly.py` replay its raw evidence. [The evidence index](evidence-index.json) records run IDs and raw hashes; [the signoff](cli-scope-signoff-2026-10-01.md) states the bounded result and limits.
