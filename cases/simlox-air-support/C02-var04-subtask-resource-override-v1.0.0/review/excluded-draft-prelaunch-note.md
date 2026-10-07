# Excluded static prelaunch draft

An unapproved source manifest was generated before independent prelaunch review. No SSH preflight, native SIMLOX child, approval or raw run was created with this draft. Its contract and planned run IDs are unchanged. The draft is retained to make the subsequent guard correction auditable.

- Draft manifest: `excluded-draft-prelaunch-manifest.json`, SHA-256 `014c6be1acf803ff6cc16dbabd87408c344471dd46e9981754ebeeb9ce07ea5f`.
- Exact pinned draft runner: `excluded-draft-runner.ps1`, SHA-256 `ede2a3004f96508d60486dfbec640ac7b37e7d823cbfd1450ad0acb483b7c9be`.
- Exact pinned draft validator: `excluded-draft-validator.py`, SHA-256 `179c8d3cd2d872c3bdf082343fab1469dac35d9684c114672996e3b6a6f60aba`.
- Exact pinned draft self-check: `excluded-draft-self-check.py`, SHA-256 `358b01913c895067f10c034e6d1d97c68cca68416f9fd3e8d12ceca66f83af4c`.
- Exact pinned draft manifest builder: `excluded-draft-manifest-builder.py`, SHA-256 `adeb13b6ad4a65a324ae748c7ce9d0d6468c239940904020862cc171337b8b3d`.

All other draft source pins remain in the preserved manifest and its source bytes were not changed. The accepted C02 single-both log's planned-duration event is one physical line; the draft self-check passed that evidence. The revised validator also tolerates a synthetic line continuation. The substantive runner change requires an observed session-0 child session ID after each native process exits; a missing or other session is rejected and sealed without terminating the child.
