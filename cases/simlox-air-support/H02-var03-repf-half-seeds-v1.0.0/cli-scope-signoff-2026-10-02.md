# H02.var03 intermediate REPF native CLI scope sign-off — 2026-10-02

**Decision:** Accept the eight preselected fixed-seed REPF0.5 realizations after independent read-only replay passed 30,723/30,723 checks. Publish the bounded observed repair and discard paths; keep Issue #18 open.

## Source and execution boundary

- Direct accepted H02.var03 REPF1 source SHA-256 `82564db9cd0d3f916a87264d16d390a42bf886f5748c843070bea20e6b1c4a92`, merged in PR #240 at `430df03616992deac05fe0be41179e57b11814f2`.
- Seeds 1–8 and their input hashes were frozen in the [contract](contract.json). Exact diff SHA-256 `648340d02ee42bee080bcceb58715d18a73bf2e22a91a7d47d66399883ed1552`: all arms change `DamageItem.REPF` 1 to 0.5 and description, while seeds 2–8 also change `Control.RSEED` to the named seed. All other tables remain unchanged.
- Installed manual physical pp193/426–427 and dictionary line170 describe REPF as a 0..1 repairable fraction. The prior endpoint pair confirms model behavior at REPF0/1. This batch is one small deterministic observation set, not a probability calibration.
- Eight accepted `-02` runs used session-0 SSH and `Global\SimloxIssue18NativeQueue`, preserving GUI PID13340/session1. Each completed import, export, calculation, report and authored-table check; converter errors0, exact 24/24 row-containing table roundtrip and 12 SHA-256 sealed raw files. All eight have 72 aligned half-hour System and Stock rows plus ResultSummary.

## Event and report acceptance

The eight logs identify 23 damaged physical LRUs; 14 complete one-hour direct item repair and 9 are discarded. Seeds 2/4/6 repair all three damaged LRUs and return them to stock. Seed1 discards two, develops a persistent backorder and cancels mission three. Seeds 3/5/8 discard IDs1/3 while repair of ID2 satisfies a waiting replacement demand directly, temporarily clears the backorder and permits mission three; the last discard leaves a backorder and aircraft unready. Seed7 repairs IDs1/3 and discards ID2: ID1 returns to stock; repaired ID3 clears the third-mission backorder, and the aircraft ends ready. A direct transfer to a waiting demand is evidenced by `Backorder removed`, not by a stock-return log line.

For each seed, native mission starts, aborts/cancellation, physical spare issues, item repair/discard identities, backorder additions/removals, system replacement completions and readiness reconcile with `NDAM`, `NREPT`, `NDD`, `NWT`, `NBO`, `PNB` and ResultSummary across every report bin. There are no ordinary failures or aircraft attrition. Author replay passed 103/103 checks and binds 96 accepted raw seals; independent read-only replay passed 30,723/30,723. Both verdicts are indexed in `evidence-index.json`.

The four seed1–4 `-01` runs are sealed excluded diagnostics: a copied checker had a Python syntax error and failed before writing roundtrip validation. The native conversion/report steps completed but their closures record `roundtrip checker exit=1`; they are not accepted runs. A separate prior seed1 REPF0.5 diagnostic yielded only discard and is disclosed in the pre-run contract. The corrected checker/runner were independently reviewed before all eight `-02` runs.

## Limits

The 14/23 realization count across seeds 1–8 is descriptive. The seeds were selected after a disclosed seed1 diagnostic; no 50% population frequency, independence or confidence interval is inferred. The explicit damage-specific replacement and ordinary ItemRepair rows are retained, so fallback priority is untested. Other structures, stations, modes, GUI visual behavior and cross-engine parity remain unverified.
