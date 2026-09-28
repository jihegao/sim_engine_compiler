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
contract and input hashes. A future native run must use a fresh run ID and the
new input SHA-256 from `contract.json`. The validator requires the corrected
description in the source input, native JSON roundtrip, and native report, in
addition to the unchanged A03 event, metric, warning and provenance checks.

No SIMLOX run or GUI acceptance has been performed for 1.0.1. Earlier 1.0.0
probe and SSH results remain attached to their original input and scripts;
they are not evidence for this revision. `publication_state` remains
`not_published`, and the A01/A02 parent GUI and A03 GUI gates remain open.
