# Independent staged publication review — C09.var03

Decision: **GO_STAGED**, for the exact staged snapshot reviewed on 2026-10-07. This memo is outside the live evidence index to avoid a self-reference; it was not staged during this review.

## Exact staged scope and byte checks

- The Git index contains 38 changed paths: four in the excluded v0.1.0 package, 33 in the accepted v0.1.1 package, and `cases/simlox-air-support/publication-index-v1.json`. There are no staged native run files, product code, or unrelated paths.
- All 37 staged package blobs equal the working-copy bytes. The final v0.1.1 evidence index is SHA256 `aa7eaf2e6ad531db15e638c607cfa1cff8c641ea4d5bc7183a6afd77a72a2732` on disk and in the Git index. All 65 standard source SHA256/size records match both disk and staged Git blobs, including previously published dependency files.
- All six accepted run chains have 83 matching local records: 71 raw files, six closures, and six invocations. This package adds no native run. The excluded v0.1.0 contract and NO_GO review remain byte-pinned. The final content GO review is SHA256 `9aaf43dc6c315046174f880cfb0b9082dbe84e6a56ccdfdcb140cb7b16a2d44e` on disk and in the Git index.
- `git -c core.whitespace=cr-at-eol diff --cached --check` exits zero.

## Catalog and bounded claim

The staged catalog has 485 unique publication IDs. Its first 484 entries and all non-entry metadata match `HEAD` exactly as parsed JSON. The sole new entry is `C09.var03.consecutive_reuse.readonly.0.1.1`; its package, contract, evidence index, signoff, README, and reproduction-guide links resolve. It describes an explicit P-MECH quantity release and rebooking at printed h9.28243 between two half-hour repairs, with no printed idle interval or intervening journey. It states no persistent person ID, general same-time priority, lender-shortage or TTRSS law, GUI claim, whole-case acceptance, or new native run. That matches the bounded signoff and the independent 15,892-check replay; the author reports 16,212 checks, including all 15,630 report cells across the three reused arms.

Catalog byte identities are deliberately distinct because Git normalizes line endings: old Git SHA256 `c13dd1ffe1f8bf3cc178e79aa809fc4d20e721619bda461c82bcfcd8d94a01d5`, old disk backup SHA256 `e5edc53d4e8cf01ed84718ba6a47b47b9b40e6beb0518a6ef4145892ad462fe2`; new staged Git SHA256 `dc453949203c10ee7032e4d80eff23526cf5840acddb616e3b06147a2d07caf9`, new disk SHA256 `0962583e83bb8838b31592db142cbbb87ba678dcf527ac41bdf701352354ef8a`. New disk and staged Git parse identically. No disk/Git byte equality is claimed for this catalog file.

This GO is a staged-byte and bounded-content decision. It does not approve a native rerun or infer an individual P-MECH worker identity.
