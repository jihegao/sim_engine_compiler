# I01.var07 — missing matching maintenance allocation at selected POINT

This bounded negative converter case tests a task-referenced LRU direct
repair when the selected APID has no `MaintenanceAllocation` row for that
task's category. It does **not** test a model with no allocation table at all.
Positive I01.var03 category, level and station selection remains open.

## Frozen inputs and provenance

The accepted I01.var01 stocked source is the foundation. Both inputs add
LRU-CM and ALT-CM task categories, BASE level, and a direct ItemRepair task
referencing LRU-CM. The matching input selects `AIR_BASIC`, whose
`MaintenanceAllocation` includes LRU-CM/BASE/BASE-01. The other input
selects `AIR_ALT`, which has an ALT-CM/BASE/BASE-01 row but no selected-point
LRU-CM row. The arms differ only by `Control.APID` and description; each
has one local spare, the same seed, mission schedule and horizon.

The input bytes, source descriptions and `exact-diff.json` were reused
unchanged from an earlier unpublished I01.var03 diagnostic. Those source
descriptions therefore say I01.var03. The new `contract.json` explicitly
declared the negative #2038 outcome **before** the fresh var07 native runs;
earlier var03 run IDs are not acceptance evidence. Matching source SHA-256:
`5201c389cccee418aec8aa8588e04e8b9f95ef7a77f4e8a633767f804a8a27fa`;
other source:
`c6d8c3ae578056a9236aa5e19c6889423a68670690cf327a5eaf86d863b58873`.
Exact diff SHA-256:
`a5b82da66d418462ea81b588923c7c5106b38cd71a6daec87dcd1e7b124b05c6`.

## Native observation

Two new session-0 SSH runs were serialized by
`Global\SimloxIssue18NativeQueue`, preserving GUI PID13340. Both import and
export the 23 row-containing authored tables exactly. The AIR_BASIC control
converts with zero errors (notice #2034), produces a valid SXO/report and
repairs failed LRU ID1 from h10.1667 to h11.1667 after the h9.8829 failure;
the failed item returns to stock. Its System and Stock reports contain 72
aligned half-hour bins.

The AIR_ALT run records `Form: TaskCategory`, rec1 error #2038, “No
maintenance allocation defined for task category: LRU-CM,” and converter
Errors:1. It leaves only a four-byte unusable SXO and produces no JSON
report or simulation event log. Its native calc process exits 0, which does
not override the converter failure. The runner accepted this arm only after
matching the predeclared error text, error count, four-byte SXO, absent
report, and successful import/export check. The fresh control sealed 12 raw
files; the expected negative sealed 9. Both closures bind the contract,
source and installed executable/manual/dictionary fingerprints.

This establishes only a converter rejection for a referenced LRU-CM/BASE
ItemRepair when the selected APID contains a different category. No AIR_ALT
readiness, repair, inventory, mission, or reorder outcome can be inferred
from that rejected model. General missing POINTs, positive I01.var03
selection, GUI visual behavior and cross-engine parity remain unverified.

## Reproduction

Run `build.py` and `describe_diff.py` to verify frozen bytes. On the
licensed Windows host, run `run_native_ssh.ps1` for `matching` and `other`
from session-0 SSH, with fresh immutable IDs. The native runner checks the
host mutex, GUI identity, exact source hashes and arm-specific converter
outcome before sealing raw files. `validate_negative.py` replays authored
assertions, while `review/independent_readonly.py` is a separate read-only
replay. `evidence-index.json` records local run IDs and all SHA-256 seals.
Raw native artifacts stay local and Git-ignored.
