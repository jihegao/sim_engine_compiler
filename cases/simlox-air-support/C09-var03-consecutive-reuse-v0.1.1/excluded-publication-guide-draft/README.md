# C09.var03: consecutive use of a borrowed pool quantity

This package is a retrospective, source-bound classification of three accepted C09.var04 fixed-seed runs. It creates no native run. The remote arm prints one P-MECH quantity travelling BASE-02 to BASE-01 at h8.53243–8.78243, working on aircraft 0 at h8.78243–9.28243, being deallocated and booked to aircraft 1 at h9.28243, working until h9.78243, then returning by h10.2824. The two work spans touch at printed time resolution; the quantity is explicitly released and rebooked. The log does not identify a persistent individual person.

The two critical failures occur at h8.28243 and h8.46988. The h8.53243 event is the return/repair request. Some immutable historical C09.var04 prose describes h8.53243 as a failure time; the native log and this contract use the observed failure times.

The matched local arm repairs sequentially with no station journey. The remote-disabled arm has no transport or repair completion through h36. These controls bound this one observed trace. They do not establish a general scheduling priority, return rule, lender shortage response, GUI behavior, or performance claim.

## Reproduce the read-only checks

From this directory, with the accepted raw run directories at the paths pinned in [contract.json](contract.json):

```powershell
& 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' .\check_reclassification.py
& 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' .\self_check.py
& 'C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' .\review\independent_replay.py
```

The author checker passes 16,212 checks. The separately authored [independent verdict](review/independent-verdict.json) passes 15,892 checks. Both reconcile all 5,210 cells across the six report tables in each arm (15,630 total). The author mutation harness rejects nine changed report cells, including a subepsilon zero-count change. Timing bounds apply only to fractional quantities derived from finite-precision printed times; nulls, IDs, whole-bin values, and discrete counts are exact.

The v0.1.0 contract and its independent NO_GO review remain preserved. That draft incorrectly described continuous booking and left an opening for report self-comparison. v0.1.1 requires the explicit release/rebook line order and an event/source-derived expectation for every report cell. The accepted native runs and historical sources were not changed or rerun.

This README describes the bounded evidence. The shared `../publication-index-v1.json` is authoritative for current publication status; the contract's `not_published` value records its prepublication snapshot.
