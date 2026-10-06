# C03.var01 staffing contract review — 2026-10-07

**Decision: NO_GO_CONTRACT** for `contract.json` SHA-256 `cc0d43a522d2aa94608db9755bb1539f1ede7d220427a796ae66fca38e8b2428`. The frozen accepted-source evidence-report hash is invalid, so the contract cannot pass its own provenance gate.

## Blocking pin

`accepted_source.evidence_report_sha256` is the 62-character literal `c775be70b01efec0bfb8c8b8de22332a96a566a4951ba7975ab0e53b87f6c0`. Accepted C03 `evidence-2026-09-29.md` has local and published Git SHA-256 `c775be70b01efec0bfb8c8b8de22332a96a566a4951bafb7975ab0e53b87f6c0` (64 characters). Preserve this contract as a failed draft; correct the literal in a new frozen version and independently re-review before replay or publication.

## Other checks

- Catalog `C03.var01` plans personnel capacity 2/1/0. The dedicated local branch is based on `origin/simlox/main` at `388f74a046ca2c389ff21a2d79875e9196c69f78`; no same-name remote branch was found. The accepted C03 1.0.2 source has 16 published tracked files. Local and Git bytes match except the deliberate `.gitignore` dual identity: local CRLF eight-byte SHA-256 `8d22814e19ac1121bcdcfb89aa88c9da384ec98d2f31f90cedc7a29f95b5f17f`, published LF seven-byte SHA-256 `127672b43b817aa8f10c44cdb48d4eeef8c0201da894e8a2430cce505ab49933`.
- Accepted C03 contract and original independent-review hashes match. The C02 single-both and A03 formation prerequisite input hashes and installed manual hash match. The three named final inputs and closures match their literals; each closure's 11 raw SHA/size seals passes (33/33). Every input has 20 row-containing authored tables and a six-table native report with 5,210 cells.
- Across the three source inputs, only the shared P-CREW `ResourceAllocation.RQTY` changes 2→1→0. Staff2 logs two simultaneous h7.5–8 crew leases, formation launch h8 and success h9. Staff1 logs sequential leases h7.5–8 and h8–8.5, formation launch h8.5 and success h9.5. Staff0 logs no work or launch and one mission cancellation h8.5. These are physical ID-specific, fixed-seed observations, not a general priority or deadline rule.
- The proposed complete System, StockTotal and Resource half-hour reports, summary and total reconciliations are observable. ResourceResultsTotal `NRUM` is approximately 1/36 in both positive arms; `NRW` is 0, 1/72 and 1/18 for staffing 2/1/0. `ResourceResults.NRA` must not be inferred as the complement of occupied workers.

No native or GUI call and no accepted source/raw edit was made in this review.
