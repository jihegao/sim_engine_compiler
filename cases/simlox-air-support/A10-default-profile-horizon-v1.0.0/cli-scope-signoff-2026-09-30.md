# A10 generated default profile at 48 and 50 hours: CLI scope signoff

**Decision:** `native_behavior_accepted` for the two deterministic single-aircraft default-profile horizons below; `reusable_published` after merge to `simlox/main`. The full A10 catalog case and its variants are not thereby completed.

The accepted parent is A01 1.0.0, native input SHA-256 `8bbd31d05630cc4a44c4b03b715d17e2f4a1ee1601352952089efd3e584f98b7`, with its existing CLI signoff. The A10 48-hour and 50-hour frozen inputs are SHA-256 `3362c767cc64cf58b7ec6c2de59cc865a122626cf3c67f16772c4baa35fe246a` and `a8cc2d4933df9e873b19061dc853a9862b9627b88624684f62cb699d73334a1e`; the [exact source diff](exact-diff.json) is SHA-256 `56aa3ce40f3c6e4a8ad56f00abb87d781d2ce971487f8c59d40c49f8d71f0190`. The frozen [contract](contract.json) SHA-256 is `98deedbf37f7b34cbcd78a626885ad49c89cbd9cc094a65e98c3d126e392f88f`. Both remove the parent's explicit mission/profile/operations rows, set one aircraft's operational use to 0.25 hours per hour, and add `SystemDeploymentUtilization.MISSIONS=1/12` per hour; only the horizon, result collection end and description differ between variants.

The installed 2017 SIMLOX manual is SHA-256 `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`. Printed pages 194–195 document default operational profiles and the 48/50-hour examples. Page 194 has an `mclen` comparison inconsistent with those examples. The native timelines, not that comparison, are the accepted observation.

Sealed session-0 SSH native runs `a10-default-48h-20260930-01` and `a10-default-50h-20260930-01` have closure SHA-256 `f071e72016750daf2bdc7a930a5925dfde3ae9fadc91db39dfcc69d55c69a09e` and `013f5428f95c9aef9770961c4ef74ceb971864304aac45cafea6ae961ac0d218`. Each has five completed steps, the global Issue #18 queue mutex, unchanged source fingerprints and preserved GUI PID 13340/session 1. All 11 populated business source tables import/export exactly; conversion logged zero errors, warnings #108/#126 and four notes. The native event log allocates `<TEACH-AIR-01,0>` to each of four generated `<TEACH-UNIT_TEACH-AIR-01_MISSION>` waves:

| Horizon | Four starts | Four completions | Each duration | `NSYMO` and `FTMO` integral |
|---|---|---|---:|---:|
| 48 h | 4.5, 16.5, 28.5, 40.5 | 7.5, 19.5, 31.5, 43.5 | 3 h | 12 aircraft-hours |
| 50 h | 4.4375, 16.4375, 28.4375, 40.4375 | 7.5625, 19.5625, 31.5625, 43.5625 | 3.125 h | 12.5 aircraft-hours |

All four missions log success and completion in each run. Native reports contain respectively 96/100 half-hour system and stock intervals, one initially and terminally ready/available aircraft, zero failures/PM, and no stock demand/movement/waiting. `ResultSummary.MSTF=MSUF=0` because these implicit missions are `CONTINUOUS`; event evidence and `MTMF=STMF=1` are used for this scope, without reinterpreting fixed-mission fields.

The [author validator](validate_native.py) SHA-256 `1e870479b670c22f392e2f25a643521d601b4401c2e3cddc71a9a4aea34e4c16` passed; its saved [report](review/author-native-validation-2026-09-30.json) is SHA-256 `a118d48284f7699cb641ee7236b1fa685b015b4aed84ddf96ade8bd267cf444d`. The separate [read-only reviewer](review/independent_default_profile_readonly.py) did not import the author implementation or run native software; its script SHA-256 is `bb6b07051b672986c6553516dcce1c32afacce1eb9802423bcd185fd8e6af72d`, and its [62/62 passing report](review/independent-default-profile-2026-09-30.json) SHA-256 is `592eb9756622ba0fe0ef15a4c34d6152bf5e2afceb97e8e2487701d4fd47c8d1`.

Raw `.sxi`, `.sxo`, logs and reports stay in local ignored `runs/`. The source and review artifacts here are sufficient to recheck the published observation; a new native run requires a fresh run ID in the guarded session-0 environment. General default-profile generation, explicit profile suppression, multiple aircraft/types, GUI Profile View rendering, failure/PM interactions and cross-engine parity remain unverified.
