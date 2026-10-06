# C03.var01 — shared crew capacity 2/1/0

This package classifies three **already accepted** C03 1.0.2 CLI runs. It adds no model input or native run. The [corrected contract](contract.json) pins the accepted source, final run IDs and raw closures. The v0.1.0 contract and its independent NO_GO remain excluded.

The three inputs differ only in the shared BASE-01 P-CREW quantity: 2, 1 or 0. All retain two physical aircraft, a two-aircraft formation mission, and a half-hour crew-dependent preparation task for each aircraft. At capacity 2, both aircraft prepare concurrently from h7.5 to h8 and the mission succeeds at h9. At capacity 1, the crew transfers from aircraft 0 to aircraft 1 at h8; the mission launches h8.5 and succeeds h9.5. At capacity 0, both requests wait without a crew booking or preparation work and the mission cancels at the observed h8.5.

The [author replay](check_reclassification.py) passed **16,955/16,955** checks on two runs with identical verdict bytes. It checks the accepted Git and local source bytes separately, all 33 raw SHA/size seals, the 20 row-containing authored-table roundtrips, physical events, and every cell of all six reports: **5,210 cells per arm**. The separate [independent replay](review/independent-postrun-review-2026-10-07.md) passed **18,091/18,091** checks.

This is one fixed-seed source-bound staffing comparison. It does not establish a general aircraft priority, crew regrant rule, or cancellation deadline. [Scope signoff](cli-scope-signoff-2026-10-07.md) records the limits. The evidence index pins final source bytes and reused raw seals; independent publication review remains required.
