# B04.var03 notice during turnround — independent read-only replay

**Decision: GO_BOUNDED, 4,162/4,162 independent checks.** This is a retrospective classification of the single accepted B04.var05 native run `b04-var05-turnbreak-v010-ssh-20261006-01`. No B04.var03 native child was run. The standard-library [replay](independent_replay.py) SHA-256 is `437133907d5f0fabc7ed92135ce00d5cffc987a5fb9f4a7d0d377746f9c2bfa8`; the deterministic [verdict](independent-verdict.json) SHA-256 is `3ae97a4e6e92c8dee0cbdc76eab22bd307a10bd1ab99f59328646b0d383e715a`. Two executions produced identical verdict bytes.

## Evidence checked

- Reclassification contract SHA-256 `cdae7dc60ab3593e48514811f9e4635bcc00f26f11039f3a189eeb4d1479e798` and independent contract memo SHA-256 `990eb30ddb127de1e3409dec04255451ba452c0b6782b68b8ff92b6bd639161a` match their frozen pins.
- Accepted source input SHA-256 `965a3acc431696e56b760b07323e4cf11cb571e030885fff708787ce84f3e42f`; accepted independent verdict SHA-256 `fe9deac260919c28a7b5ee410f22d798d7d562de5b764d35b28d208bd0947fff`. All **21 published source SHA/size pins** match both disk bytes and `HEAD` Git blob bytes. The original native input copy is identical to the accepted source.
- Accepted closure SHA-256 `58a4838596f96e07d5d20fff3cc4e02a7d3ef07f539d61f3a5c5caf0ca84b545`, invocation seal, unchanged before/after source map, and **13/13 raw SHA/size seals** match. Its six native steps completed, recorded SSH session 0 and GUI PID 13340/session 1/start 1790590196826, and conversion gave Errors 0, Warnings `#108`/`#126`, Notes 0. The raw report SHA-256 is `df1c6055ce7cd32dea0e02112ab752bc34ec2484311e7d0baa44b04910a1c87a`.

## Observed chronology

The same physical aircraft `<TEACH-AIR-01,0>` flies both missions. Mission identity ending `0` launches h21.5 and succeeds/completes h23.5. Its turnround task 1 starts h23.5; SEQ1 performs h23.5–23.6667 and SEQ2 performs h23.6667–24. At h23.75, while SEQ2 is active, the next mission is ordered, created, activated, and **preassigns** that aircraft. The log has no physical allocation or preparation of that mission before turnround completion.

At h24, SEQ2 and turnround task 1 complete and `System arrives` is logged; only afterward does the mission identity ending `1` physically allocate the same aircraft and begin preparation. Preparation ends h24.5. Launch occurs h24.75, and success/completion h26.75. The second turnround completes h27.25, leaving the aircraft ready at the 36-hour horizon. The review checks the identities, timestamps, and log order separately; it does not infer a general same-time event priority from the h24 print order.

The replay independently integrates ready, preparation, reservation, operating, and turnround intervals into all **72×40 SystemResults cells**, checks all **72×16 StockTotalResults cells** against no stock demand/backorder, and checks the 11 ResultSummary and one description cells: **4,044 report cells** in total. Both missions succeed, no cancellation, failure, PM, stock or crew-wait state is reported, and the terminal aircraft is ready.

## Limits

The evidence supports only this one source-bound early-notice/preassignment observation, with later physical allocation. It supplies no matched later-notice control, independent native replication, arbitrary notice-lead conclusion, GUI visual proof, or general engine ordering rule. The original accepted run and its raw files were read only; no author validator was imported or used as authority.
