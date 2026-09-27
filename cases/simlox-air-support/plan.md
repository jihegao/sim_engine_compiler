# A01/A02 case-library slice plan

This is the frozen scope and history of the A01/A02 implementation slice. For the expanded manual-based plan and execution order, use [progressive catalog v2](progressive-catalog-v2.md).

Source: main `595cb5eee9987324b19a8c3566f201f937e05f15`; issue #18 is the 26-case catalog. This branch owns only reusable templates, catalog/index, native validation and A01/A02. PR #15 and its evidence are read-only. The aircraft is a transparent teaching asset, not a real F35/J35 or an equivalent model.

1. **Contracts before models.** Freeze one stable aircraft/base, one mission template, zero preparation/fault/PM and no active stock or resource constraint. State explicit hours/minutes, notice/start/end, repetition schedule, busy/ready, flying-hour integral, horizon and stop accounting. A02 changes only the number/timing of non-overlapping instances. Record any native-required inert rows and roundtripped defaults.
2. **Reusable package.** Create the 26-entry planned catalog, capability index, known-issues summaries, per-case contract/parameters/mapping/manifest/results/evidence index, and generator. Keep A03–F04 planned. Use immutable run directories under `data/local/simlox-case-library/v1/<case>/<run-id>`; check that Git ignores these outputs.
3. **Validation and native execution.** Pure Python validators check source SHA, nonempty business-row roundtrip, import/calc errors, SXI/SXO size, report/log parsing, warning classification, event counts/times, flight-hours and stopping semantics. Negative and positive tests must execute behavior. Native runner checks process occupancy and tool/input hashes, never touches another GUI process. Request coordinator SSH PowerShell runs with exact script/input SHA and paths.
4. **Independent replay.** After first valid A01/A02 runs, request fresh directories using documented public commands and compare event identities and values. Preserve raw exports and any normalized copies separately. GUI calibration/review is pending private user handoff; record exact checks, do not claim GUI-first order or reusable publication.
5. **Delivery gate.** Commit narrow artifacts and evidence summary. A02 may be a provisional CLI derivation of A01 while GUI acceptance is pending. No Rust/default J35 changes, 1000-sample campaign or speed ratio. Bundle this branch for coordinator PR against main; never merge.

Stop conditions: any conversion error, 4-byte/absent SXO, missing report/log, unexplained warning, or changed parent field outside A02's declared delta prevents behavioral acceptance. Native CLI success does not satisfy the GUI publication gate. Do not infer equivalence to J35 from these teaching cases.

## Execution status (2026-09-27)

Publication review follow-up: the four prior normal/replay runs are retained as
**legacy unsealed** evidence. A corrected validator now checks full mission and
aircraft instance identities, each 30-minute FTMO/NSYMO/NSYMA/NSYMR/NSYRY
interval and explicit zero unrelated mechanism counters. A new runner writes an
invocation before launch and seals raw hashes afterward. The coordinator ran
four fresh immutable normal/replay runs serially; all four passed fresh strict
validation, and manifest/acceptance/evidence records were rebuilt from those
results. Each run has a distinct invocation ID and raw-artifact closure.
The five existing collection-window runs were reanalysed read-only in
`collection-window-review-v2.json`: at 7.5 h the mission is notified and
pending, not in flight. Original validation and raw exports were preserved.

- Contracts, 26-entry catalog, A01/A02 generators, checked native inputs and parent diff: **implemented**, commit `891ac7c`.
- Native runner and pure validators: **implemented**. A01/A02 final and fresh independent replay: **CLI behavior verified** in four immutable runs. Initial zero-duration preparation-row candidates failed the no-preparation contract and were preserved.
- Observation probes: SIMPE-shortening matrix **rejected** by converter `#204` with 4-byte SXO in all five early cells; 10.5/12 h positive controls **valid**. RCEND-only matrix **verified** native report clipping in five cells. This does not establish simulation-stop semantics.
- GUI calibration/review: **pending private handoff**. A01/A02 publication stays provisional; A02 has only a provisional CLI parent. AMD128 cross-engine pairing: **unverified**.
- A03-F04, full J35 equivalence, 1000-sample comparison and equivalent speed ratio: **outside this slice / not performed**.
