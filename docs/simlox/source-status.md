# Status

**Complete for source-side collection.** Four previously timed examples were checked. All four original Demo models, run 1 models, and matching existing run 1 results were exported, for 12 raw files. All export processes exited 0. The run logs name their input and output files, and all four result summaries report 1000 replications.

`aircraftorg` is directly relevant to aircraft support: the description identifies Fokker F28 aircraft, deployment is 4 aircraft at ARN and 6 at CPN, and it has missions, repair locations, item structure, and stock. `wbend` and `wbT2fix` also contain aircraft systems (`SA39`, `AIRCRAFT` group) and operational missions; `wbT2fix` adds a constrained `TESTER` resource. The Torpedo Case supplies clearer explicit task, preventive maintenance, and multi-resource relations, though it is not an aircraft example.

**Pairing:** Verifiable at the prior run log/path level for all four run 1 model/result pairs. It is not independently embedded in the result export as an input digest.

**Blockers for later semantic alignment:** `sim_engine_compiler` at `e9b6391` and canonical `simulation_inputs` were not examined in this source-only workspace; their schema/values still require pairing. SIMLOX report settings were not explicitly supplied, so unexported report tables and percentile settings remain unknown. The Torpedo Case result has documented map and percentile warnings. Original Demo and prior run 1 exports have schema differences, so their complete transformation history is not proven here. No simulation equivalence is claimed.

See `manifest.json` for source/output paths, sizes, hashes, executable version, exact commands, settings and summaries; `provenance.md` for association and caveats; `relation-inventory.md` for semantic table evidence; and `raw/` for unmodified exports.
