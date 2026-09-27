# AMD128 J35 source snapshot

This is a source and compile snapshot, **not a runtime oracle**. It was collected from `/home/g/Models/spare_mvp` at clean `main=origin/main=0e709bdcc2d692d9cfed49b9037c76ef71aefe33` on 2026-09-26. The project identity is `project-j35-8aircraft-43day-availability-20260909`; its read-only database `payload_json` had SHA-256 `bce310581ae8b2fdf1fcd28f76065a673e63746f9b39be5152393d5c67287a7e`. No database file is retained here.

| File | How obtained | SHA-256 |
| --- | --- | --- |
| `project-export.json` | Upstream `ProjectJsonExporter(repo_root=root).export(payload)` | `aa285af2abcea77d8244f16599284259d4a3ac57288ee0b5afc8a626566744d7` |
| `simulation-inputs.json` | Upstream `SimulationAdapter(root).compile_scenario_with_gate(exported, model_family="aircraft_support_v1")`; gate `compiled`, 0 issues | `30c20086cbf400dd35e132f71498c1d05c256d74a1384355b703ccc713601559` |
| `execution-plan.json` | This repository's `scripts/compile_execution_plan.py` using `legacy-minute-v1` | `44cfed9a8006b002369e7934cbef02fabf797003b3db39f3169b306a4f3b42eb` |

The canonical input fingerprint is `d9aa54e27d152bab775e3653a1025e42457ea9900e454849ec0d65c6c9cc65c5`; the Plan fingerprint is `08b74f0b7d345d12fa9b62f62221eb38aa0d443167e97018333ea5b61b47ab2f`. They are hashes of normalized structures, distinct from the file byte hashes above. The SIMLOX mapping and native validation are documented in [the J35 candidate record](../../../../docs/simlox/j35-page-candidate.md).
