# A08.var06 invalid SCHEDULED plus IQTYD converter boundary

This negative case derives from the accepted [A08.var02 input](../A08-var02-random-count-equidist-v1.0.0/cli-scope-signoff-2026-09-30.md). The [frozen contract](contract.json) changes only `OperationProfile.ITYPE` from `RANDOM` to `SCHEDULED` and a provenance label, leaving `IQTYD=<POISSON>` in place. The installed SIMLOX manual defines `IQTYD` only for `RANDOM` initiation and documents converter error #212. The [builder](build.py) and [exact diff](exact-diff.json) bind the source to its parent.

The guarded session-0 SSH run imports and exports the JSON model, preserving all 13 populated source tables. Calculation reports exactly one error #212, with warnings #108 and #126. SIMLOX returns process exit code zero but creates only a 4-byte `.sxo`; no JSON report exists. This is a converter rejection, so no mission behavior is accepted from the invalid model. The author [replay](review/author-rejection-validation-2026-09-30.json) passes 39 checks and a separate [independent read-only replay](review/independent-rejection-2026-09-30.json) passes 49.

Reproduce source with `python build.py` and `python describe_diff.py`; replay the sealed local run with `python validate_rejection.py`. New native execution requires a fresh run ID, session-0 SSH, the host-wide mutex and preservation of GUI PID 13340. Raw artifacts remain under ignored `runs/`.

This scope covers one installed executable and one `SCHEDULED+<POISSON>` input. It does not establish behavior for other invalid combinations, GUI visual content or other engines.
