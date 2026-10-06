# C03.var01 staffing contract review — 2026-10-07

**Decision: GO_CONTRACT_ONLY.** Reviewed `contract.json` SHA-256 `652f886c5d22eaaa20f605812695055586af81209b99682d357112a8c903043f`. This approves a bounded, read-only reclassification design; it does not approve a checker, publication package, or new native run.

The preserved v0.1.0 contract SHA `cc0d43a522d2aa94608db9755bb1539f1ede7d220427a796ae66fca38e8b2428` and independent NO_GO memo SHA `56c51d69301a8bc0056b1f51e971d8aea2fb262ecb66413d4434a1f980bdce1d` identified a 62-character accepted evidence-report pin. The v0.1.1 diff changes only version and that literal; the corrected 64-character SHA `c775be70b01efec0bfb8c8b8de22332a96a566a4951bafb7975ab0e53b87f6c0` matches the accepted C03 evidence report on disk. Accepted C03 contract and independent-review hashes also match.

The three named final C03 input and closure hashes match. I recomputed all 33 raw file sizes and SHA-256 seals across staffing 2/1/0 with zero mismatches. The accepted package's 16 published source identities and deliberate `.gitignore` local CRLF versus published LF distinction, C02/A03 prerequisite input pins, and installed manual pin were checked in the preceding v0.1.0 independent review; their literals are unchanged here.

The source comparison is limited to the one shared P-CREW `ResourceAllocation.RQTY` value 2/1/0. The frozen gate requires physical aircraft and crew lease identity, the three distinct observed mission outcomes, exact authored roundtrips, and every cell of six report tables per arm. The source-bound 30-minute concurrent and serial work, 30-minute staff1 wait, and 60-minute two-aircraft staff0 request wait are falsifiable against the accepted logs. The contract correctly avoids treating `ResourceResults.NRA` as a free-worker complement and limits conclusions to these fixed-seed CLI runs. There is no general priority, deadline, or capacity-policy claim.

No checker, native or GUI process was run, and no accepted source or raw file was edited.
