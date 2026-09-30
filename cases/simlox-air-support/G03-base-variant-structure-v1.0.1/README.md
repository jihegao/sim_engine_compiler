# G03 BSID variant source and operation probe

This bounded package derives two one-aircraft inputs from accepted A01. Both define a base system with one installed LRU and a `BSID` variant. `add` adds a second LRU through `ItemStructure`; `exclude` gives the inherited base LRU `QTYPM=0`. Only the variant is deployed, so its SID is visible in the fixed mission lifecycle. All item failure rates are zero.

Run `build.py` to reproduce or verify the frozen JSON inputs, then `describe_diff.py` to replay the exact A01-to-child table delta. `run_native_ssh.ps1` requires a session-0 SSH shell and uses `Global\SimloxIssue18NativeQueue`; its two original run IDs and raw file hashes are in [evidence-index.json](evidence-index.json). The raw `runs/` contents stay local and ignored by Git. `validate_native.py` replays the author's assertions; `review/independent_readonly.py` independently checks the source and raw evidence.

The [signoff](cli-scope-signoff-2026-10-01.md) defines the accepted scope and its limits. In particular, the default report does not expose the effective inherited item list or failure/repair propagation.
