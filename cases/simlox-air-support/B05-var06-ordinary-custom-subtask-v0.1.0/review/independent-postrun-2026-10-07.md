# B05.var06 ordinary custom subtask — independent read-only replay

**Decision: GO_BOUNDED, 12,704/12,704 checks.** This reclassifies only the two accepted B05.var03 native runs; no B05.var06 native run was made. The saved standard-library [replay](independent_replay.py) SHA-256 is `00997afb155f78c6ddc1f18a542aa001b3e1e4e36580b6df0da2225d5ff35b54`. Its deterministic [verdict](independent-verdict.json) SHA-256 is `9a62faf5c17e27bea795b7d2beecceec9ddfb95bf13ead0cba4191945ddda8f7`; two executions yielded identical verdict bytes. An initial reviewer-only stage-list expectation omitted the already recorded `check_import_export` stage; it was corrected before this final replay. It did not reflect a native failure.

## Frozen source and native seals

- Classification contract SHA-256 `7a87b8d51a44b6fc0e5ed03324e6ac362eac8ca1b264a9644b7b9a55b3122706` and contract-review memo SHA-256 `99f0392705f5d84a8705b06614658f3f12d1e8ceac58d1fcc80f4c79ad43e7c3` match. Ordinary input SHA-256 `37423c0c127a014d082c740780eee8531e877c405bcd537918b8fc1e4289892b`; predefined input SHA-256 `2fc3b10f9a17db8dc4cc4fa4810d79ef9231775c1fcb658303742ad15e41fc46`. The accepted independent review and six selected source files match their frozen hashes and published `HEAD` Git bytes.
- Ordinary closure SHA-256 `f8edd2fa92e8dc68e37a87b7f457b9fe644e89baa963424ab9a34eaf2ee14245`; predefined closure SHA-256 `e47ddd60c4ccba0750ddebacd948a1feedfcb46322eb6f288d82843d2b3fdad4`. Both invocation seals, before/after source maps, 12+12 raw SHA/size seals, SSH0 guarded stages, valid output, and converter Errors 0/Warnings `#108` and `#126`/Notes 0 reconcile. Every authored cell in all **17 row-containing tables per arm**, including three all-null placeholders, survives native import/export.
- The pair changes only `ProblemDescription.PDESC` and the `TaskBreakDown` SEQ1 `SUTID`: ordinary `INSPECT` versus predefined `<INSPECT>`. Ordinary `SubTaskType` defines both `INSPECT` and `SERVICE`; `PREP-FIXED` references them at SEQ1 duration 1/6 hour and SEQ2 duration 1/3 hour. The predefined arm retains the definitions, SEQ2 and both durations.

## Event and report replay

Both sealed model logs are byte-identical. On physical aircraft `<TEACH-AIR-01,0>`, generic subtask 0 SEQ1 performs h7–7.166667 and generic subtask 1 SEQ2 h7.166667–7.5. Preparation completes h7.5; the mission launches h8 and succeeds/completes h10, leaving one ready aircraft. There is no cancellation, backorder or resource-wait event. The native log uses generic subtask labels; the **source plus exact roundtrip** is the evidence that the ordinary SEQ1 binds to authored `INSPECT`.

The checker independently integrates the ready, preparation, reservation and operating intervals into every one of 72×40 System cells in **each** arm; it checks each of 72×16 Stock cells, all 11 summary fields, and the authored description. Each report has 4,044 cells. All non-description cells match between arms. The summary is `[1,0,36,1,0,1,0,1,0,1,0]`; no failure, PM, stock demand or wait is represented.

## Limit

This is one fixed-seed preparation pair and retrospective source-bound classification. Equal event logs and reports do not establish equivalence of custom `INSPECT` and predefined `<INSPECT>` semantics in other tasks or inputs, other custom IDs, GUI visual behavior, or a new B05.var06 native replication. The accepted raw runs and owner files were read only.
