# C04.var01 v0.1.0 contract review — NO_GO_CONTRACT

Frozen contract SHA256 `0f9acd39449e62f205d61b4219229e5d4eb7a2992be4a098c420d66749723d3d` (31,618 bytes). This was a read-only review; no new simulator or GUI process was invoked.

## Evidence that passes

- All 25 accepted C04 source records match disk and published Git SHA/size pins. The selected final `crew-equal`, `aircraft-missing`, and `crew-zero` input, parent-diff, invocation, closure, log, report and 33 raw SHA/size seals match. The direct C03 staffing-1 contract/evidence/review/input/closure/invocation/11 raw seals and staffing-0/2 input pins match. The installed manual pin matches. The excluded horizon-wait log matches and its SXO is four bytes.
- `crew-equal` is the matched positive control with `DTIM=0.5`. Against it, `crew-zero` changes only `ResourceAllocation.RQTY` 1→0. `aircraft-missing` jointly changes `SystemDeployment.QTYPS` 2→1 and `ResourceAllocation.RQTY` 1→2. `crew-before` has a byte-identical successful log/report but uses `DTIM=0.51`, so it is an output corroboration, not the sole-delta source comparator.
- Both shortage arms cancel at h8, before their declared h8.5 latest launch. Aircraft-missing allocates only physical ID0, successfully books P-CREW, completes one preparation and releases the crew. Crew-zero allocates IDs0/1, records two failed P-CREW availability tests and no work or lease; both waiters stop on cancellation. The generic `mission cancelled:` line has no reason code. These are distinct source-bound trace classifications, not an isolated single-cell causal effect for aircraft-missing.
- Each report has six tables and 5,210 cells. Against equal, aircraft-missing table-cell differences are exactly `0/4/158/0/218/5`; crew-zero differences are `0/4/16/0/219/5`. ProblemDescription and StockTotalResults match. The declared System/Resource occupancy, work and waiting intervals are observable in the raw reports.

## Blocking evidence wording

The third acceptance bullet requires GUI PID13340/session-1 identity and **responsiveness around each of four** import/export/calc/report steps. The accepted C04 runner records session 1 and responsiveness only at preflight. After each command it verifies and records same process PID/start presence, not session identity or responsiveness. A separately versioned contract must state the evidence precisely: responsive PID13340 in session 1 at preflight, same PID/start identity present after each step. This is the same factual boundary corrected in C04.var02 v0.1.1.

The source-panel C03 lineage sentence also deserves clarification: against C03 staffing-2, aircraft-missing changes both `QTYPS` 2→1 and `DTIM` 1→0.5; equal and crew-zero each change only `DTIM` versus their respective C03 staffing inputs. The contract already discloses the two-cell aircraft-missing contrast against equal, so this is a clarity correction rather than a separate physical-evidence failure.

No native replay, checker implementation, or publication is approved by this memo. The corrected contract needs a fresh contract-only review.
