# C09.var02 v1.0.1 frozen static preflight: NO_GO_PURE_PREFLIGHT

**Decision:** NO_GO_PURE_PREFLIGHT. This review binds the first frozen 235-record prelaunch manifest, not any subsequently corrected bundle. No v1.0.1 SSH preflight or native child was launched for this decision.

## Exact reviewed bytes

| File | Bytes | SHA-256 |
|---|---:|---|
| `prelaunch-manifest.json` | 80,641 | `7bd905f4d80c8de18999e400d883322cca2360f987162f0019d42f2541d95cd7` |
| `run_native_ssh.ps1` | 15,083 | `9d02fc25dedf1ba373e8711a45f884f8babf9539cf481a8a202e85d53be523fa` |
| `validate_native_cli.py` | 14,961 | `c8442e66e23cd9bd8656dadbe97ebb2328ee5552acc2e26c7986568a683be145` |
| `report_oracle.py` | 22,356 | `6f95539f257c74c42ad11916f4e499ebbbbdff4a9d280dda2f3ffe40a58a6899` |
| `self_check.py` | 12,513 | `2ded703af8386517f63d4a8de2a5ad7a2d32f2f38215b0c53ab0363e7878adea` |
| `contract.json` | 75,208 | `1ebec1583966b0a2c70043a4ba54e076763eb8d6b091192823b65c5e977e6653` |

All 235 manifest source path/size/SHA records matched current disk bytes; 235 keys were distinct. The manifest binds 78 accepted local and 78 published Git source identities, 117 accepted raw files, nine closures and nine invocations, installed manual/dictionary/executable, the two fresh input hashes, runner, validator, oracle, and the excluded v1.0.0 contract/review. Both reserved run directories were absent. PowerShell 5.1 AST parse returned zero errors. The author self-check returned 5,210 parent cells and 22 adversarial rejections; `verify_sources.py` returned the declared accepted counts. Independent reviewer checks separately passed the complete 32-table pair source comparison with five mutations, the accepted 5,210-cell report shape with four shape mutations, and accepted parent per-station P-MECH conservation with three edge mutations. These checks establish static provenance and calibration only.

## Blocking exact-value gate

The frozen contract requires exact null, identity, integer, count, and **whole-bin invariant** values; printed-time tolerance applies only to genuinely fractional event-derived values. In `report_oracle.py`, `_boundary_fields()` marks both sides of every printed half-hour boundary. `compare()` gives any integer-valued field marked by that boundary a `0.00002` allowance when the field is in its fractional-field set. This includes `SystemResults.NSYMO`.

The accepted C09 remote raw log prints `mission starting` at h8. The sealed accepted report has `NSYMO=0` for `[7.5,8)` and `NSYMO=2` for `[8,8.5)`. Those are complete-bin exact values. The frozen comparator marks both rows and would accept a mutated preceding-bin `NSYMO=0.00001` because `abs(0.00001-0) <= 0.00002`. It would likewise accept `2.00001` in the following bin. A zero or integer count cannot acquire a fractional allowance merely because a timestamp is printed at the interval boundary. The 22 author probes do not cover this case. This is a false-positive path for the full 1,754-cell-per-arm gate and blocks native launch.

## Recovery

Preserve this manifest and review. Correct the comparison so a source/event-derived whole-bin value is exact even when an adjacent boundary event is present. Any truly fractional event-time value should use its declared field-specific printed-time bound. Add a mutation probe changing the accepted `[7.5,8)` `NSYMO=0` to `0.00001` and the `[8,8.5)` `NSYMO=2` to `2.00001`; both must reject. Freeze a new manifest and checker hashes, repeat the full static review, and obtain an actual SSH0 PowerShell 5.1 `-PreflightOnly` receipt before any distinct GO_PRELAUNCH approval. No native run is needed to repair this static defect.
