# C04.var01 v0.1.1 independent contract review

**Decision: GO_CONTRACT_ONLY.** This approves a bounded, read-only reclassification of three already accepted C04 final runs. It does not approve a checker, publication, a native rerun, or a general causal rule.

Contract SHA-256: `eaddbcbb400107d3c8aa1f64151a04e85303448e3997efc4b22512db6b313191`. The preserved v0.1.0 contract (`0f9acd39449e62f205d61b4219229e5d4eb7a2992be4a098c420d66749723d3d`) has a NO_GO memo at `../../C04-var01-shortage-v0.1.0/review/independent-contract-no-go-2026-10-07.md`, SHA-256 `4cf248f77eb0c9212c04b88778757d075ab85cd6890b364513a0545701ab9e15`. The revised contract changes only its version, the direct C03 source-delta statement, and the GUI provenance gate. Both previous objections are resolved: the GUI must be responsive in session 1 at preflight, with the same PID/start identity present after each of four stages; the direct C03 parent comparison now distinguishes DTIM-only equal/zero derivatives from the missing-aircraft DTIM+QTYPS derivative.

## Evidence checked

- Recomputed the literal byte and SHA-256 pins for all 25 accepted C04 source files against both local files and Git blobs; the three selected final `-02` inputs, parent diffs, invocations, closures, logs and reports; and all 33 selected raw SHA/size seals. No mismatch.
- Recomputed the C03 staffing-1 parent contract, evidence, review, input, invocation, closure and 11 raw seals; staffing-0 and staffing-2 inputs; the installed manual; and the excluded horizon-wait log and four-byte SXO. No mismatch. Discovery `-01` runs and horizon-wait remain excluded.
- Checked the authored 31-table, 979-leaf, 201-row-cell source panel. Against equal, crew-zero changes only P-CREW `RQTY 1→0`; aircraft-missing jointly changes `QTYPS 2→1` and P-CREW `RQTY 1→2`. Direct C03 staffing-0/1 derivatives change only `DTIM 1→0.5`; the staffing-2 derivative additionally changes QTYPS.
- Independently read selected physical logs: equal serializes P-CREW for IDs 0 and 1 in [7.5,8) and [8,8.5), then both launch h8.5 and complete h9.5. Missing-aircraft allocates and prepares only ID0, then cancels h8. Crew-zero allocates IDs 0 and 1; both availability tests fail, there is no crew booking/work, and cancellation occurs h8. Both shortage arms cancel before the declared h8.5 latest launch, with no launch/success/completion.
- Parsed report copies without altering original bytes. Each selected report has the six required tables and 5,210 cells. Against equal, observed per-table changed-cell counts are `0/4/158/0/218/5` for missing-aircraft and `0/4/16/0/219/5` for crew-zero. The contract requires every cell across all three arms, physical cleanup, resource wait/work separation, and terminal stock/system reconciliation.

## Bounds

The generic cancellation line has no structured reason code. The aircraft-missing comparison changes two source cells jointly, so it cannot isolate a QTYPS effect. `NSYMP` includes time-weighted waiting occupancy in the zero-crew run; it must not be called physical work. The proposed conclusion is limited to these accepted source and native traces. A separately authored read-only replay must pass the frozen event, source, provenance, and full report gates before publication.
