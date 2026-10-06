# B01.var02 independent postrun replay

**Decision: GO, bounded to the sealed one-aircraft, one-mission, fixed-seed CLI run.** The standalone read-only replay passed **4,428/4,428** checks. It did not import the author's validator or run SIMLOX.

- The frozen source changes only `MissionType.NOPER` from 1 to 0.5 across 167 authored row cells. The 15 row-containing authored tables roundtrip exactly. Conversion reports Errors 0, Warnings 2 (only #108 and #126), Notes 0, with a usable SXO.
- The child closure SHA-256 is `8445912b08f9feb307d51bde3b218d5e260001c844161521360685c5e8b77776`. All 12 child raw SHA/size seals, 11 accepted B01 parent seals, and 34 A01 prerequisite seals match. The source fingerprint map matches before/after; the invocation records SSH session 0, an `sshd.exe` ancestor, the global queue mutex, and preserved GUI PID 13340/session 1/start 1790590196826 through five successful stages.
- Native event order is mission order/creation/allocation, preparation start and performance at h7.5; preparation task completion/end and mission launch at h8; task work h8.5–9.5; mission success, completion, and aircraft return at h10. Only aircraft physical ID0 appears, with no cancellation or fault/PM task.
- Every value in 72×40 System, 72×16 Stock, 11 summary, and one description field was checked against the accepted B01 report. Stock, summary, and description are identical. Exactly nine System cells change, confined to rows 14–16 around h7–8.5, as independently specified by the shifted preparation/notice ledger. The final System row records one ready aircraft.

This is an observation of the frozen source and installed CLI; it does not establish a general same-time event priority, other notice values, or GUI presentation.

Artifacts: `independent_replay.py` SHA-256 `a1591e3974520946e24528c9dfc90b4347550bf93801dd1b68148d964e6380c5`; `independent-verdict.json` SHA-256 `3a38c25b5f2d8296cbb232c40d775ff234e5bb4e5272ed9238201c3b3f186b6a`.
