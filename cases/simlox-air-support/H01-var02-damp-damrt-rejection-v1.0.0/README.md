# H01.var02 simultaneous DAMP and DAMRT rejection

This bounded pair starts from the accepted [H01.var02 rate source](../H01-var02-rate-no-consequence-v1.0.0/cli-scope-signoff-2026-10-02.md). The control is byte-identical. The child changes only `MissionDamage.DAMP` from 0 to 1 and the problem description, leaving `DAMRT=3,000,000` per million mission hours and the zero-probability attrition consequence in place.

Two serial guarded session-0 SSH runs exactly roundtrip all 16 authored row-containing tables. The control converts with zero errors and reproduces ten rate-generated BATTLE-HIT events across three successful fixed missions. The child converter reports error `#253`, stating DAMP and DAMRT cannot both be used for the mission/damage combination. Its output is a four-byte stub, with no model event log or JSON report. A zero calculation process exit is not treated as simulation acceptance.

The [frozen pre-run contract](contract.json), [exact source diff](exact-diff.json), [CLI sign-off](cli-scope-signoff-2026-10-02.md), and [evidence index](evidence-index.json) bind this installed-converter observation. The rejected child establishes no simulated damage behavior. Other values, intermediate DAMP, positive consequences, GUI visual behavior and cross-engine parity remain unverified.
