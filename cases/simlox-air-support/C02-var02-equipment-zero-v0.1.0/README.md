# C02.var02 equipment unavailable v0.1.0

This package classifies the accepted C02 serial joint-resource pair for the catalog's C02.var02 question. It reuses the original [C02 1.0.2 native runs](../C02-joint-resources-v1.0.2/README.md) and launches no new simulation.

Both inputs retain one P-CREW and jointly require one P-CREW plus one E-GSE on INSPECT SEQ1. The 10-minute INSPECT and 20-minute unresourced SERVICE breakdown, aircraft, mission, seed and description are identical. The only source difference is `ResourceAllocation.RQTY` for E-GSE, one versus zero. Both final native imports/exports preserve the authored row-containing tables.

With E-GSE available, crew and device are booked before h7 INSPECT work and freed after ten minutes; SERVICE completes h7.5, the mission launches h8 and succeeds h10. Without E-GSE, the native availability test passes for P-CREW and fails for E-GSE; neither resource is booked, no work or launch occurs, and cancellation is observed at h7.58333. Each original report has six tables and 5,210 cells, including 72 half-hour System, StockTotal and Resource rows.

The [contract](contract.json) received independent preflight GO. The author checker passes 53 checks and a separate independent replay under `review/` passes 11,252, including all 5,210 report cells per arm. Both read the original source and raw files without modifying them. The [evidence index](evidence-index.json) pins their published Git and local byte identities, two closures and 22 raw seals. The accepted C02 `.gitignore` has local CRLF bytes and published LF bytes; both hashes are retained separately.

This fixed-seed device-zero observation does not establish a general all-or-none allocation rule, personnel shortage, delayed delivery, substitution, shifts, contention, GUI visuals, cross-engine parity, or full C02.var02 and Issue #18 completion.
