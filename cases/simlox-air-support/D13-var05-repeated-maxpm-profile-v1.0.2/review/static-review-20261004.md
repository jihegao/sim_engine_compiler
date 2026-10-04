# Independent static review: D13.var05 MaxPM repetition

**Decision: bounded GO for v1.0.2 direct `<LIMIT>` repetition.** The v1.0.0 and v1.0.1 subprofile arms remain excluded diagnostics. This review does not accept MaxPM subprofile equivalence.

## Source and manual

- The v1.0.2 contract is SHA-256 `e8a9405243cee781873e565a7c6852cfd923e4c62240896fb2a24e20585f1b27`, matching the literal pre-run runner pin. Flat input `fde24c914f94b2f945c3c55aa485972289ddc5e6ea449388bd22c25477977604` and comparison input `45e6a3a835d81ebddbf30369f3b97093545da856a42fe1c94f0aa49712948c60` match the contract and closure. Current builder SHA-256 is `80f3a07acfcb6e278abc53a31f5aeaac6926ccf7f66f130393ce243a53e3dfb2`; runner is `5717507e6ce3a471d2d04c287b73ff7003da6df20637cc58858fe9b59a09b03c`, matching the run's before/after seal.
- The accepted D13.var03 rise parent input, closure and sign-off are pinned in the contract and runner. The source pair differs only in `ProblemDescription`, `Unit.MAXPMP` (`CAP-FLAT` versus `CAP-REPEAT`) and `MaxPMProfile`. Flat contains nine adjacent periods over h0–36; comparison contains three direct `<LIMIT>` rows with `IQTY=3/IINT=12`. Expanding those three rows at h0, h12 and h24 gives exactly the flat periods. The file label `nested` is historical runner naming; it contains no subprofile reference.
- Installed manual SHA-256 `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`, physical pp376–379, identifies MaxPMProfile, `<LIMIT>` rows, IQTY/IINT repeated building blocks and the prohibition on overlapping explicit periods. It discusses subprofiles too, but v1.0.2's actual rows test direct LIMIT repetition only.

## Sealed native evidence and exclusions

- v1.0.2 closure SHA-256 `a211a9ae4de16a66a535ac618e83f191f837291af89a678eaae29ba011698812` seals 22 raw files and stable sources. Eight session-0 SSH steps completed with exit 0 and GUI preservation; invocation records the global queue mutex and GUI PID 13340/session 1. Both converters report Errors 0, Warnings 2 (#108 and #126), Notes 0; there is no #331 in the accepted run. Both SXOs are usable and authored populated cells roundtrip.
- Flat and comparison native event logs are byte-identical, SHA-256 `da72bad471923d27cce8eeb08377e461dbf833776eabab4547c1bbb0b5977ada`. The two CAL24 tasks are created at h24, physically work h24.25–25.25 and h24.75–25.75, and both complete. All three missions succeed. ResultSummary and every SystemResults/StockTotalResults row agree across arms; each table has 72 half-hour bins and terminal ready count is two. The separately authored read-only checker reports bounded GO 853/853; its script SHA-256 is `bebfc7bbb098eab263e61fa2a4afcb78dd8bd69c1efceddf79df734d263a1d39`, verdict SHA-256 `659eec22c218b86e88a4aa6513a15b2e6f36391e265bd73a0987b301de236c2c`. The author checker is separate and reports 132/132; its result is not a substitute for the independent replay.
- v1.0.0 root-first closure `709f7b25aea6444e0804799848b847dcd71a6219faced3921ee20ac87dfb6c79` and v1.0.1 child-first closure `ee2d46157a3286742ca08b442578ad10c60ddd9cd5df6ab9c128c90df260604f` are correctly excluded. Both comparison arms had converter warning #331 (`ETIM is not valid for sub profiles. Data Ignored.`) and no physical PM through h36, unlike their flat arms. Reordering the child rows in v1.0.1 did not recover equivalence.

## Scope and wording

This supports direct LIMIT repetition parity for this one seed, two aircraft, one CAL24 PM, three repetitions and 36-hour horizon. It does not establish nested subprofile behavior, hidden capacity-counter operation, other cycle lengths or GUI behavior.

The sign-off now states the row-count distinction accurately: 30 flat and 24 comparison authored rows include three all-null placeholders in each source, leaving 27 and 21 rows with values. Populated authored cells are preserved. No substantive blocker remains in this static review.
