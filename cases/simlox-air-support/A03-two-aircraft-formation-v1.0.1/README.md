# A03 1.0.1: correct the native case description

This is a new, unpublished A03 candidate. It keeps the A02 instructional parent
and the A03 1.0.0 two-aircraft behavior contract. The only revision to the
SHA-256-pinned 1.0.0 native input is `ProblemDescription.PDESC`: it now names
the two-aircraft, one-wave teaching case. The `revision-diff.json` records that
single table change. The `parent-diff.json` separately records the four changed
tables from frozen A02: `MissionType`, `OperationProfile`,
`ProblemDescription`, and `SystemDeployment`.

`python3.12 build.py --check` verifies the checked input without rewriting it.
The version-local SSH runner, validator and strict validator bind the new
contract and input hashes. Any further native run must use a fresh run ID and
the input SHA-256 from `contract.json`. The validator requires the corrected
description in the source input, native JSON roundtrip, and native report, in
addition to the unchanged A03 event, metric, warning and provenance checks.

The 2026-09-29 [native and GUI evidence](evidence-2026-09-29.md) records a
fresh source-bound SSH run, independent raw-artifact audit, and GUI calculation
of an identical native SXI copy. Earlier 1.0.0 probe and SSH results remain
attached to their original input and scripts; they are not evidence for this
revision. The frozen `contract.json` and native run manifest retain their
pre-run status text and hashes; the dated evidence is the later acceptance
readout. `publication_state` remains `not_published`.
