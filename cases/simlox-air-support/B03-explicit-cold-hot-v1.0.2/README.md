# B03 1.0.2: explicit cold and hot preparation

This package derives directly from the published [B02 1.0.2 input](../B02-serial-preparation-v1.0.2/native-input.json), SHA-256 `fc9e80de0ac8515f3d3a7fe4a2c9aa916bce23ba5b05e13e2f69857230d9dc34`. Its other prerequisite is the [A02 signed repeated-wave scope](../A02-single-aircraft-repeated-missions/cli-scope-signoff-2026-09-29.md). The old `preparation-resource-v1` B03 is a semantic reference only; it uses the unpublished B02 parent and different aircraft/mission identities. Its 2026-09-27 isolated run is not this case's native evidence.

The [contract](contract.json) freezes `explicit-mission-type-v1`: the 08:00 mission is `COLD-FIRST` with ordered 10- and 20-minute `INSPECT`/`SERVICE`; the 12:00 and 16:00 missions are `HOT-SORTIE`, each with one 10-minute `HOT-SERVICE` step. The same aircraft performs all three. Each mission type has a one-hour notice and a two-hour flight, preserving B02's timing fields. Recipe selection is by explicit MTID. No sortie-history or thermal-state switching is claimed.

The [exact parent diff](parent-diff.json) changes only six tables:

| Table | Declared delta and reason |
| --- | --- |
| `MissionType` | Replace `BASIC-MISSION` with `COLD-FIRST` and `HOT-SORTIE`; both retain all B02 timing and formation fields. Explicit MTIDs choose recipes. |
| `OperationProfile` | Rebind the 08:00 row to `COLD-FIRST`; add `HOT-SORTIE` rows at 12:00 and 16:00. This exercises the A02 repeated-wave path. |
| `MissionPreparation` | Rebind B02's row to `COLD-FIRST` and add a `HOT-SORTIE` row pointing to `HOT-PREP`. The 45-minute scalar remains distinct from the breakdown duration on both paths. |
| `Tasks` | Keep stable `PREP-FIXED`, clarify its cold description, and add `HOT-PREP` for the hot recipe. |
| `SubTaskType` | Keep stable `INSPECT` and `SERVICE`; add `HOT-SERVICE` to make the hot path distinguishable. |
| `TaskBreakDown` | Keep B02's ordered cold rows unchanged and add one 10-minute `HOT-PREP` row. |

All other tables, the aircraft/site IDs, seed, 36-hour horizon, half-hour reports, and the B02 cold task/step IDs are unchanged. The exact generated input SHA-256 is `9c6b3c8955089b89caa1a71634eb78e9fd52069d5d710273e3a6bc710e19222c`; the parent diff SHA-256 is `b1480f9f3f414feb84ab08448f156e25aee15d8ee1e90e56fb652d1f87a13283`.

Run `build.py --check` before native work. `run_native_ssh.ps1` requires a fresh run ID, exact input hash, authenticated session-0 loopback SSH, the host-wide native mutex, and the original responsive GUI PID 13340. It runs import, roundtrip export, calculation and report export serially, then seals raw files. `validate.py` checks source-bound native behavior. `review_readonly.py` independently replays raw files without importing the builder or validator. Failed run directories are retained and never reused.
