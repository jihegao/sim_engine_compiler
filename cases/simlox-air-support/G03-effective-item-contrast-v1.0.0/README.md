# G03 effective item participation contrast

Four fixed-seed inputs extend the accepted [G03 source package](../G03-base-variant-structure-v1.0.1/README.md) with the accepted D01 local repair method. Only one item has a positive `OPHOURS` failure rate in each input. The base control deploys the base system; the other three deploy a BSID variant. The native event log distinguishes an inherited base LRU, an added variant LRU, and the excluded base LRU.

Run `build.py` to verify the frozen JSON inputs and `describe_diff.py` to replay their table deltas. `run_native_ssh.ps1` uses the guarded session-0 SSH path and the host-wide SIMLOX mutex. Original raw runs remain in ignored `runs/`; [evidence-index.json](evidence-index.json) records their IDs, lengths and hashes. `validate_native.py` and the independent `review/independent_readonly.py` replay the resulting assertions separately.

The [signoff](cli-scope-signoff-2026-10-01.md) defines the bounded result and its remaining limits.
