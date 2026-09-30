# A11 explicit formation priority and fallback: CLI scope sign-off (2026-09-30)

**Decision:** `native_behavior_accepted` for the bounded three-run explicit-formation behavior below; `reusable_published` after merge to `simlox/main`. A11's remaining boundaries stay open under Issue #18.

## Source and lineage

The published A11 mixed-type parent input SHA-256 is `4e1387b15457485de42ae20b1f0ed6382c013603c0bfc6de75d753339c2a7213`. The three [frozen inputs](README.md) are `ab-high` `483c958b91738e53dbd9a88319707e263addd1c6ecd6a723d749fbfd3aa3a15f`, `aa-high` `9d3115f9d6c67414fe9d1813ecd028a8eb88976e6f3f65bbb08384bdba911f3a`, and `b-missing` `78170c663abfae5112da49ab034b28a0c9274bd46d130e2c5f17f2050b0643c8`. The [exact diff](exact-diff.json) SHA-256 is `3e0c54c100a1847ae882b66ec86300f94cd75d6e07f4c9203c62a9451343afe4`; [contract](contract.json) SHA-256 is `7308d0657ca5ebf5bf9687518a880c2535c6a38213d3ff4387babb28573de2b9`.

All three add `Formation`, `FormationSystem`, and `MissionFormation` to the parent, defining complete AB and AA combinations. `ab-high` and `aa-high` differ only in the two `MissionFormation.PRI` values and description. `b-missing` keeps AB at higher priority but removes B deployment, updates the unit description, and otherwise matches `ab-high`. The inherited `MissionSystem.NOS=MNOS=1` for each A and B stays in all three inputs.

The installed SIMLOX 2017 manual SHA-256 is `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`; pages 184–185, 281–282 and 292–294 define the formation tables, precedence over quantity requirements, and priority/complete-formation search. The proprietary manual remains local.

## Native evidence

Final session-0 SSH queue runs `a11-form-ab-high-20260930-01`, `a11-form-aa-high-20260930-01`, and `a11-form-b-missing-20260930-01` have closure SHA-256 values `1cbedb2f29746882292b03082c44feb1a8231f0bb56c986c742e711c4e7f7e89`, `490774b99f3891e77a7d057f9fc39d66db758b3dc7be5bb7deb3055f6a84d01b`, and `9795c5b05c08589937385a4cf0b0a31d1ca175f02e573746f226f2108eed5f2a`. Each seals 12 raw files and stable source hashes. The runner preserved GUI PID 13340 and held `Global\SimloxIssue18NativeQueue`. All five native steps passed, 17 populated source tables roundtrip exactly per input, and conversion reported zero errors. The three warnings in each run are #108 (log) and #126 twice (two item-free teaching system definitions).

| Input | Native active formation at hour 8 | Aircraft flown | Ready at 36-hour end |
|---|---|---|---:|
| AB priority 1, both types deployed | `FORM-AB` | A#0+B#2 | 3 |
| AA priority 1, both types deployed | `FORM-AA` | A#0+A#1 | 3 |
| AB priority 1, B undeployed | `FORM-AA` | A#0+A#1 | 2 |

Each mission logs success/completion at hour 10 and four aircraft mission-hours over 72 half-hour system bins. The AA-priority run's explicit `FORM-AA` launch despite inherited `MissionSystem` B minimum proves the observed formation override in this setup. The B-undeployed run demonstrates selection of the complete lower-priority AA formation with no incomplete AB launch. Its native log does not expose the internal rejection of AB; interpreting the selection as fallback also uses the frozen priorities, unavailable B deployment, and manual rule. No general internal search trace is claimed.

The [author validator](validate_native.py) SHA-256 is `084c05cde36f0551d62217b0929656fbc4a28ab12400f35a9a6fe0a71e7e1cd8`; its [saved replay](review/author-native-validation-2026-09-30.json) is `1c810c66215ee4b87bf1b63c101667e16a55a16f47b441cb88cd61ded1da7ad5`. A [separate read-only reviewer](review/independent_formation_readonly.py) SHA-256 `e6fdd9745c4ff8be8d2b173a58c53bcff5570ca6ccc9943eeecc1b973858d129` passes [81/81 checks](review/independent-formation-2026-09-30.json), SHA-256 `a414bbac3f2e78ffe4715f61f82100ec2ded59edd4e6816bbaddb96d9f327bb6`, without author validator imports or native re-execution.

Raw native `.sxi`, `.sxo`, logs and reports remain in ignored local `runs/`; the repository tracks the source, replay tools, exact diff, and evidence hashes. Reproduce source with `python build.py` and `python describe_diff.py`; replay final evidence with `python validate_native.py` and `python review/independent_formation_readonly.py`. A fresh native run requires a new run ID and the pinned local GUI/session environment.

Unverified: equal-priority rejection, `ALOAA` continuation-only semantics, later readiness, reconfiguration, failures, positive-duration preparation, competing missions, group/subsystem references, GUI-only behavior, and cross-engine parity. Issue #18 remains open.
