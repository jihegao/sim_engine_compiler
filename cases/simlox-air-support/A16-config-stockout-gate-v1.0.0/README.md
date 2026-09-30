# A16: unavailable B configuration item

This paired control changes only the baseline description and B local spare size from one to zero. It keeps the A/B `CBSID` definitions, task breakdown, mission schedule, seed and other source rows. The accepted E02 zero-stock source is a form donor.

`build.py` and `describe_diff.py` verify the frozen source and exact parent delta. The guarded `run_native_ssh.ps1` generated one immutable native run under ignored `runs/`. `validate_native.py` and the separate `review/independent_readonly.py` replay the raw result. [The evidence index](evidence-index.json) records its hashes; [the signoff](cli-scope-signoff-2026-10-01.md) states the bounded result and limits.
