# Independent v107 run review — NO_GO_RUN

The one approved native child `c09-var02-v107-shortage-ssh-20261007-01` is **NO_GO_RUN**. The frozen author behavior check failed with OS exit 1 and `AssertionError: `, and the run has an immutable failure seal. The original approval and reviewer method do not accept this run.

## Provenance and completed stages

- Contract SHA-256 `2051fca4baf9555adaab28d870726eee97fe38ac61537630d6b63d2b89a5bb99`; manifest has 1,726 records, all matched by both source maps and current pinned bytes. The unchanged prelaunch receipt and approval bind the sole child ID.
- Closure SHA `e09f5fa2549c088e4c3e25a9dc3acea660cac9e1331f4a012e3acaa981810715` seals 23 raw files; failure-seal SHA `1a8cbc59efeeae35bc30af33854bf85121b9cdb73dc5f84b2a20ea4e8650ee3a` seals those plus closure and invocation. Independent SHA/size checks passed every sealed file. Source hashes before and after match all 1,726 manifest records.
- Six captured children have session 0, actual integer OS exits `0,0,0,0,0,1`, no capture error and GUI-preserved flags. Import, export, checker roundtrip, calc and report export completed. The converter log has exactly Errors 0, Warnings 3, Notes 1 with the expected 108/126/292 contexts. The behavior checker is the failed sixth stage; native execution stopped there.

## Exact trace discrepancy

The sealed `model.log` line 218 prints return transport task 0 starting at h9.46988 with `transportation time: 0.5`. Lines 219–220 show that same task arriving and the P-MECH receipt at BASE-02 at h9.59488. The observed departure-to-arrival interval is **0.125 hour**. The HOME PM resource is regranted and work starts at h9.59488; work completes at h9.84488. The outward loan, borrower repair/release and HOME failed availability/wait retain their matched source and event identities.

Both frozen author `physical_ledger.py` and frozen reviewer `independent_replay.py` assume the printed return-duration label must equal elapsed event time. They reject the unaltered raw log. This is a false-negative implementation gate for analyzing actual elapsed time, but it does **not** turn the failed run into accepted evidence. The raw annotation is an observed conflicting field whose interpretation needs a separately declared retrospective contract.

The new read-only diagnostic `review/independent_failed_run_diagnostic.py` (8,725 bytes, SHA `9813ac63ae13a8b77d8b9c0ae40a8669e00cc5c7cc6d0f6996f70934f98bee11`) keeps the original log bytes sealed. For **parser isolation only**, it changes that one printed `0.5` label to `0.125` in memory, changing no timestamp, task ID, station, quantity or raw file. With the event edges unchanged, the separate reviewer trace and source/event oracle reconcile all 1,754 child report cells. An in-memory ResourceResults.NRW cell mutation of `+0.00001` is rejected. This synthetic substitution is not a classification replay and is never grounds for promoting v107.

## Recovery boundary

Preserve v107 approval, source, raw, closure, failure and reviewer method unchanged. A new retrospective contract may examine the sealed child as a bounded counterexample, explicitly retaining both the printed `0.5` label and actual `0.125` elapsed interval and deriving the report directly from unaltered raw. It must keep the v107 prospective run NO_GO and make no general TTRSS or logger-rule claim. No v107 rerun or downstream native action follows from this diagnostic.
