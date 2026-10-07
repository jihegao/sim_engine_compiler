# C09 accepted boundary-value calibration

This receipt supplements the preserved `independent-pure-preflight-no-go-2026-10-07.md`; it does not approve the frozen C09.var02 v1.0.1 bundle or change its NO_GO decision.

I parsed each sealed accepted C09.var04 report from a normalized **in-memory** copy, leaving raw bytes untouched. For the 18 affected SystemResults/ResourceResults state or fractional fields (`NSYRY`, `NSYMA`, `NSYMO`, `NSYMP`, `NSYRP`, `NSYPM`, `NSYWR`, `NSYUA`, `NSYA`, `FTMO`, `STACC`, `NR`, `NRA`, `NRUM`, `NRW`, `NRRT`, `NRRI`, `NRRO`), I inspected 1,296 numeric values per arm. None has a nonzero residue less than 0.00025 from an integer.

| Accepted arm | Raw report SHA-256 | Values scanned | Near-integer nonzero residues |
|---|---|---:|---:|
| local | `6925130e220a8add532bab29de41741703b8dad0e3f274adf43571b40e407d50` | 1,296 | 0 |
| remote | `3d08b8226c76ac9b57029d38e1c21294e9a08be76150c6d2fdc10f9b020cd33f` | 1,296 | 0 |
| remote-disabled | `24eb61f53890146580ecee52e90d93495154a38f9e0d76401a0475e5a6cda3d0` | 1,296 | 0 |

The remote log's `mission starting` at h8 comes from its scheduled source. Its report has exact `NSYMO=0` in `[7.5,8)` and `NSYMO=2` in `[8,8.5)`. This exact source-fixed boundary differs from a genuinely fractional interval reconstructed from a native event time printed at limited precision. The scan cannot prove all future child rows will be exact; it shows no accepted C09 evidence for allowing a near-integer residue in a complete-bin zero/count. A corrected comparator should identify genuinely fractional event-derived cells individually and keep whole-bin counts exact.
