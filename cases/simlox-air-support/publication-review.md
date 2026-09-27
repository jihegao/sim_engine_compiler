# A01/A02 publication review follow-up

This follow-up corrects the false positives found in the first CLI validator.
It does not change the A01/A02 model input, default runtime, J35 Plan, PR #15,
or any earlier raw/validation file. The prior delivery is archived outside Git
at `..\pre-publication-review` in the task directory.

| Review finding | Repair and executable regression |
| --- | --- |
| Prefix-colliding aircraft, wrong instance, mission ordinal 999 and another-aircraft ready events passed | `validate_native.py` now checks complete event bodies and native mission/aircraft instance tags through notification, creation, activation, allocation, start, task, success, completion and ready transitions. `test_exact_lifecycle_and_ready_identity_reproducers` mutates each identity and requires rejection. |
| Equal flight-hour total concealed wrong interval placement or zero operation state; repair count could be nonzero | Every 30-minute SystemResults row is compared with the fixed allocation, reservation and flight intervals for FTMO, NSYMO, NSYMA, NSYMR and NSYRY. Relevant fault, PM, repair and preparation counters must be zero. `test_per_interval_state_and_mechanism_mutations_rejected` shifts FTMO to 0–2 h with the same total, zeros NSYMO and sets NREPT=1; all fail. These zero counters do not constitute resource-capacity conformance. |
| A changed input and roundtrip could be paired with stale SXI/SXO/log/report | `run_native_bound.ps1` creates `invocation.json` before native execution and `closure.json` after it. The binding records run and case paths, input/schema/contract/parameter/generator/validator/runner/binding hashes, SIMLOX executable identity, exact arguments, invocation ID and all raw hashes. Strict validation rejects missing or tampered binding and raw files. `test_binding_rejects_tampered_pre_closure_and_mixed_raw` exercises these paths. Old unsealed runs remain read-only historical evidence. |
| Cached old pass was attributed to newer validator | `build_case_records.py` calls strict fresh validation for each run, verifies pre/post bindings and requires the cached run validation to equal the current result. Tests reject old cached passes and a changed fresh result. The manifest names both invocation and closure hashes. |
| Pairing omitted prelaunch allocation and ready time | `pairing-contract.json` embeds both full contracts and SHAs, native input/accepted-evidence hashes, full instance identities, notice/allocation/ready transitions at 7/19/31 h, restoration at 10/22/34 h, and FTMO/NSYMO/NSYMA/NSYMR/NSYRY integrals. The test verifies the embedded contracts, fingerprints and 33/27 ready hours. Cross-engine execution remains unverified. |
| At 7.5 h, a future 8 h launch was called unfinished in flight | `validate_collection.py` separately counts notified-pending, in-flight and completed at the requested end. `collection-window-review-v2.json` reanalyses all five old RCEND runs read-only with the analyzer SHA and original raw/validation hashes. At 7.5 h: pending 1, in flight 0, complete 0. Tests recheck all five current derived observations and raw hashes. Printed ties do not establish internal event priority. |

Four new immutable runs, `a01-bound-final-20260927-03`,
`a01-bound-replay-20260927-04`, `a02-bound-final-20260927-03` and
`a02-bound-replay-20260927-04`, were executed serially by the coordinator.
Each has a distinct pre-launch invocation, four exit-zero native steps, zero
conversion errors, exact nonempty business-row roundtrip, nonempty SXI/SXO,
complete ENLOG and a sealed report. Fresh strict read-only validation and
`build_case_records.py --refresh` passed. The per-case `evidence-index.json`
contains exact raw paths, sizes and SHA-256; the manifest records source/tool
hashes and both invocation/closure IDs. The A01/A02 README commands use the
bound runner and fresh run IDs.

CLI behavior is verified for this teaching slice. GUI calibration/review is
pending the private user login; the task-level `requested-gui-checks.json`
points to the newly accepted SXI files. This is a provisional CLI deliverable,
not full issue #18 publication or a J35 equivalence claim. Native SIMPE
crossing behavior, AMD128 pairing and the separate J35 cancellation and nested
replacement contracts remain unverified. No 1000-sample campaign or speed
ratio was run.
