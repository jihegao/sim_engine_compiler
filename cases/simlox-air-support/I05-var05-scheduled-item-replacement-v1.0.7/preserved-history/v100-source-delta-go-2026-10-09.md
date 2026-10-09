# I05.var05 independent source-delta review — 2026-10-09

**Decision: GO_SOURCE_DELTA_AND_PARENT_BYTE_CUSTODY_ONLY.** This review covers the unfrozen I05.var05 source candidate and the current byte identity of the accepted H02.var04 fallback evidence. It does not approve a child native result.

## Reviewed bytes

| File | Bytes | SHA-256 |
| --- | ---: | --- |
| `contract.json` | 9,416 | `edc1a4f545b475a31ac59662bd1e0ef9506a46963ef3c04b9c33198ae8896186` |
| `README.md` | 3,181 | `4ed9c94039498a36aa4e664bd8f84c472312f63bec9f821ea419700f39d3df01` |
| `build.py` | 4,042 | `7191e524baf7b3f5c9b87c17a020d93bd3e130dac5bcab2887b05ceecdfe9dfc` |
| `check_source_delta.py` | 9,273 | `2cc8a59d7f7f329adc1614fb40e3676ee18b35e1e5618d63361e99e5b81856f8` |
| `native-input.json` | 51,336 | `c30b0849ad46a6351e4c94a2964f0f6f16274b6b926508b8fe47ecd9a5323480` |
| Accepted H02.var04 `fallback-input.json` | 47,775 | `2e29c2ea72304544c68281e8629bd242cca3d6252cbbe7cea2c48e0a00716a97` |
| Accepted H02.var04 `evidence-index.json` | 7,650 | `bad27eb48f2767db7e26d4209935576c8aefc3e7124c64741cbfcac65692157e` |
| Accepted H02.var04 scope sign-off | 3,102 | `53b9b4152f5f48d5d0003f0d4ad0257b5e5e933892dc85db2c810f8b6ee3681d` |

I independently parsed the parent, contract, and child JSON with duplicate-key and nonfinite-number rejection and compared values recursively with exact types. The 35 parent tables are the exact prefix of the 36 child tables. The sole existing-cell change is the contract's exact `ProblemDescription.PDESC` before-to-after text. The last table is `ChangesItemReplacement` with the eight reviewed native column objects, one `instance_name=""` instance, and the sole row `["TEACH-AIR-01", "TEACH-LRU-01", "BASE-01", 5.0, 1.5, null, null, null]`. Removing that table and restoring the PDESC cell reproduces the full type-exact parent, including the unchanged `ItemReplacement` row and all model settings.

The accepted fallback run is `h02-var04-item-fallback-v100-ssh-20261002-01`. Its evidence index lists 12 original raw artifacts. I independently read all 12: every current byte length and SHA-256 matches its indexed seal. For each file, the size, modification time in nanoseconds, Windows attributes, permission mode, and hash stayed stable across two read-only reads. The observed attributes are **32** and mode **438** for all 12; these originals do **not** have the filesystem read-only bit. The updated source checker verifies those observed attributes and mode, the indexed byte seals, and before/after metadata and hashes without writing to the accepted parent.

The installed manual (SHA-256 `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`, physical pages 504–505) and dictionary (SHA-256 `11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0`) support the existing-target `MID/IID/STID/TIMEC` change. The proposed h5 `SURPT=1.5` activity duration remains a child hypothesis, not an observation.

## Limits

- This is a source-delta and current byte-custody review. I did not execute the builder, source checker, accepted parent methods, SSH, or SIMLOX native behavior.
- “Read-only” describes how the parent evidence was accessed. This review makes no claim of filesystem read-only attributes, Windows ACL ownership, or reparse-free ancestry. The checker does not establish ACL ownership or reparse ancestry.
- This decision does not freeze these sources or approve preflight, SSH, native execution, publication, or Issue #18 completion. Those require separate gates.
