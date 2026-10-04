# K09.var01 CLI scope sign-off — 2026-10-05

**Decision:** Accept one bounded report-settings comparison from a single accepted J05/A01 SXO as reusable native CLI evidence for Issue #18. The [contract](contract.json) was frozen before the fresh v1.0.1 run. The v1.0.0 run remains an excluded diagnostic because its parent byte-identity hypothesis failed. [Independent verdict](review/independent-verdict.json): `GO_BOUNDED`, 263/263 checks.

## Frozen source and settings

The parent [J05.var01–02 sign-off](../J05-collection-window-v1.0.1/cli-scope-signoff-2026-10-01.md) SHA-256 is `8c30b1b1a563c2350431fe7978eea12ae8c33bd112584dc3b53006d509ba9e95`; its baseline input SHA-256 is `8bbd31d05630cc4a44c4b03b715d17e2f4a1ee1601352952089efd3e584f98b7`. The sealed parent run `j05-baseline-v101-20261001-01` closure SHA-256 is `544ac02924741dae7f002b6bc3bb5c3002fe6b2d0f4a4cdd88088c5d5fd3c5ad` and SXO SHA-256 is `d0f7290327d70c17c1bc6d41c3a19ba966773d58d7c9b587770a89def7f506a7`. The accepted parent had native import/export roundtrip, zero converter errors, an 8–10 successful mission and 36-hour horizon.

The installed `Default.sxs` SHA-256 is `1c2bb5380a2ac2e57fd3f0c782794154d331100c2bec2206d0caa430d3e21a5d`. `make_report_settings.py` constructs `mission-enabled.sxs` SHA-256 `ce17b329540fadf72b6256c9ead15913ce853bf847b5d09a2ef98cf56a6c57e5` by changing exactly eight bytes inside `MissionSettings` from `N` to `Y`; file length and every other byte remain equal. The installed manual SHA-256 `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`, physical pages 143–149 and 168/171, documents report settings files, table selection and `-report`/`-rpts`/`-rjexport` CLI use. Proprietary binaries and manual are retained locally.

## Observed three-export contrast

| Export | Report SHA-256 | Tables beyond the four common tables | Mission result bins |
| --- | --- | --- | ---: |
| `default-a` | `0e1e59e7fdbe1aa72b6daa41d28cd205cfbe61066398084985215852edf01602` | None | 0 |
| `mission-enabled` | `f2f7ea55ea14f36d6bd7db3c5a82d71a69f9b03df80d5773e664eab8f3d1d465` | `MissionResults`, `MissionResultsTotal`, `FixedMissionResults`, `FixedMissionResultsTotal` | 72 |
| `default-b` | `0e1e59e7fdbe1aa72b6daa41d28cd205cfbe61066398084985215852edf01602` | None | 0 |

`default-a` and `default-b` are byte-identical. All three fresh reports have identical `ProblemDescription`, `ResultSummary`, `SystemResults` and `StockTotalResults` tables, including their columns and rows. Those four tables' columns and data rows match the accepted J05 baseline report: 72 half-hour System and Stock intervals from 0–36, system ready before h7 and after h10, one mission assigned h7–10 and operating h8–10, and no stock demand or backorder. The new mission-specific report has 72 half-hour `MissionResults` bins and a fixed mission row at h8 with `NMREQ=NMSTA=NMSUC=1`, `MTREQ=MTACC=2`, and mission/system completion fractions 1. The original model event log records mission start h8 and success h10.

The older J05 parent JSON is **not** byte-identical to the new explicit-default exports (parent SHA-256 `b9b7d970e7f12763f0098eb2d2c546cc2ed2b68792840e74f2175fcd4ca14099`). The fresh explicit exports include `report.database_version=0`; their System and Stock `instance_name` fields are empty whereas the parent populated them. The columns and rows named above are equal. This difference is part of the accepted observation, not normalized away in raw evidence.

## Reproduction and limits

The fresh run `k09-var01-report-settings-v101-ssh-20261004-01` has closure SHA-256 `8f3a2f79cbf52a7e0b13ce079af183052c7a2a50fc66764b487cd1da4a885c19`; the excluded run closure is `c73732c9391c635b9a51a29fafe9576e71ed67e5cafe13e6b4e5ba4e3acc9364`. Each has three completed session-0 SSH report-only steps, source hashes before and after, GUI PID 13340/session 1 preservation, and eight sealed raw files. The [evidence index](evidence-index.json) records their 16 raw file hashes. The separate reviewer replay checked source lineage, exact settings delta, raw seals, report table/row equality and the mission timeline, passing 263/263 checks.

This establishes report table selection and row-data preservation for one previously simulated fixed-seed SXO and these two settings. It does not establish generic byte-identical regeneration across earlier invocation styles, GUI appearance or formatting, graphical output, other SXOs/settings, database export, cross-engine parity or full K09 behavior. Product `main` and the protected GUI remain unchanged.
