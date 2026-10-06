# C02.var03 contract review — 2026-10-07

**Decision: NO_GO_CONTRACT** for `contract.json` SHA-256 `03a0381bce2dd60013709f8acbda0041d5e10c0887414ed2e9edf71b93e6ff34`. One accepted-source SHA literal is wrong; freeze and correct the contract before replay or publication.

## Blocking pin

`accepted_source.evidence_report_sha256` declares `9b6015e9bb0781d35436caa077ecd5021a113997c7f2fdcbbd4595adb6069b94`. The accepted C02 `evidence-2026-09-29.md` has local and published Git SHA-256 `9b6015e9bb0781d35436caa077ecd5021a113997c7f2fdcbdd4595adb6069b94`. The literal differs at hex character 49 (`b` instead of `d`). The frozen gate requires this pin, so the current contract cannot pass its own provenance check. Correct the literal in a new frozen contract and re-review that version.

## Other checks

- Catalog `C02.var03` plans the both-resources-sufficient boundary. The contract limits the claim to the accepted C02 1.0.2 fixed-seed four-run panel and disclaims a topology-isolated single-cell experiment. No C02.var03 owner was found by the stated local/remote branch checks; the contract correctly does not treat an inaccessible GitHub PR-list query as proof of absence.
- Accepted C02 contract and original independent-review hashes match. The four named inputs and final `-02` closures match their literals; all 44 closure raw SHA/size seals pass. All 18 published C02 tracked source files match local bytes except the deliberately separate `.gitignore` identities: local CRLF eight-byte SHA-256 `8d22814e19ac1121bcdcfb89aa88c9da384ec98d2f31f90cedc7a29f95b5f17f` and published LF seven-byte SHA-256 `127672b43b817aa8f10c44cdb48d4eeef8c0201da894e8a2430cce505ab49933`.
- Within each topology, both-versus-zero sources differ only in E-GSE `ResourceAllocation.RQTY` 1→0. Across topologies the single INSPECT SEQ1 duration is 0.5 h, whereas serial INSPECT SEQ1 is 1/6 h plus unresourced SERVICE SEQ2 at 1/3 h. The two zero-capacity final model logs and reports are byte-identical. The two available-arm reports differ only in `ResourceResults` row h7 `NRUM` (2 versus approximately 2/3) and `ResourceResultsTotal.NRUM` (approximately 1/36 versus 1/108). Each of the four reports has six tables and 5,210 cells, so the proposed complete report-cell gate is observable.
- This comparison supports only resource occupancy under two different authored task decompositions with the same total preparation duration. The zero-capacity controls do not establish a general all-or-none rule, topology equivalence or a source-derived cancellation deadline.

No native call or accepted source/raw edit was made in this review.
