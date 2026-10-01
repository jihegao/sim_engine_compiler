# G01.var01: one traditional LRU/SRU repair chain

This bounded CLI case derives from the accepted [E01 local-spare case](../E01-local-spare-explicit-replacement-v1.0.0/cli-scope-signoff-2026-09-29.md). The [contract](contract.json) and [native input](native-input.json) were frozen before the guarded native run. [Exact parent diff](exact-diff.json), [signoff](cli-scope-signoff-2026-10-01.md), and [evidence index](evidence-index.json) define the accepted scope.

Run `build.py` to verify the source bytes against E01, `describe_diff.py` to verify the six-table delta, and `validate_native.py runs/g01-var01-v101-ssh-20261001-01` to replay author checks. The separate [review checker](review/independent_readonly.py) reads only the frozen source and native artifacts. All are read-only after the run. The original raw SXI/SXO, event log, JSON report, invocation and closure are local under ignored `runs/g01-var01-v101-ssh-20261001-01/`.

The first v1.0.0 local run is retained separately as an unpublished diagnostic: its predeclared wording said the initial aircraft failure event would identify the SRU. That event identifies the installed LRU; the SRU identity appears when the removed LRU arrives for repair. v1.0.1 corrects the contract, sets the general LRU SURP duration to 1.5 hours while the item-specific replacement remains 0.75 hours, and uses a fresh sealed native run. Raw v1.0.0 artifacts are not part of this publication.

Only one aircraft, one LRU, one SRU, local stock and one fixed seed are covered. Remaining G01 variants and GUI/cross-engine behavior are unverified.
