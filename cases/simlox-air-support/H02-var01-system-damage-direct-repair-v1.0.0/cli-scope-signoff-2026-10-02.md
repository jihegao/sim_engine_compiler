# H02.var01 native CLI scope sign-off — 2026-10-02

**Decision:** Accept the one-airframe, fixed-seed configured system-damage/direct-repair contrast. Publish this bounded H02.var01 slice while Issue #18 remains open.

## Frozen sources

- Accepted H01.var01 certain-attrition parent and byte-identical control SHA-256 `f519cd4549db879505c16bd5d4affb7e34f1db6227e71bebc27738442489d4f0`.
- Child system input SHA-256 `67eb54c6148cd17c43e050eaf3d310bf7f66b96452526614ca1af416c16d9bcb`.
- Exact diff SHA-256 `b04a16fa69da2fc30772bf45ec9200e3d8961bfeed5b1031bfe6c0876f778098`; contract SHA-256 `e56967790ab97d4e90e560d3c5a7f945fc45c8629a99bf07dd3ed277e51ad375`.
- Installed manual physical pp193,425–426,428 describes `<SYSTEM>` rectification and damage-specific direct repair; installed table dictionary fixes `DamageRepair` columns. The manual, dictionary and executable fingerprints are frozen in the contract and native closures.

## Observed events and report

The two fresh serial session-0 SSH runs held `Global\SimloxIssue18NativeQueue`, completed import, export, simulation, JSON report and authored-table check, and preserved GUI PID13340/session1. The control and child roundtrip all 16/17 authored row-containing tables. Both converters report zero errors. The child adds warning #254, stating that `REPF` is ignored for system damages; the inherited #108/#126 warnings occur in both arms. All 24 raw files match their closure seals.

The attrition control logs BATTLE-LOSS and permanent loss h8.78145, an aborted first mission, and later mission cancellations. The system child logs BATTLE-LOSS and aborts at h8.78145, h21.1446 and h32.1965. Local system DIRP tasks begin at h9.28145, h21.6446 and h32.393; each plans one hour and completes at h10.2814, h22.6446 and h33.393. Readiness is restored at those completion times. The second and third missions launch at h20 and h32; no mission succeeds because each launched mission is damaged and aborted.

Both reports contain 72 aligned half-hour System and Stock bins and one ResultSummary row. Control lost-aircraft exposure integrates 27.21855 hours through h36 and ends lost1/ready0. Child lost-aircraft exposure is zero, repair exposure integrates three hours, `NDAM=3` and `NREPT=3`, and it ends lost0/ready1. Stock rows are cell-identical. `MSTF` is about one-third in control and 1 in child; `MSUF=0` in each. The event log, not a summary ratio alone, establishes the sequence.

Author replay passed 29/29 checks and independent read-only replay passed 7,664/7,664. Their verdicts, scripts and raw artifacts are bound by `evidence-index.json`.

## Limits

The IID change and new damage repair row are coupled in this pair. The accepted observation establishes this configuration's one-hour local direct repair and later availability, without a general fallback-priority claim. One seed and one generic airframe without items do not test damaged LRU/SRU behavior, repair fraction, shortages, other direct or system repair choices, visual GUI behavior or cross-engine parity.
