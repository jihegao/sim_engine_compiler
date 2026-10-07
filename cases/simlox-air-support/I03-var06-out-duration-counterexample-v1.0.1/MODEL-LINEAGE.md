# I03.var06 v1.0.1 evidence-only model lineage (draft)

Status: contract-only proposal for independent review. No new native run, source edit, or catalog entry. The original v1.0.0 prospective contract and sole run remain `NO_GO_RUN`.

## Fixed identities

- Accepted comparator: published I03.var02 idle-crew OUT TFDT 0, authoritative `evidence-index-v2.json` SHA-256 `4060de5d7434ff675949b9eea7fb8f827ac0c72a56e530169b60ecb0da0724dc`.
- Original child input: v1.0.0 `native-input.json` SHA-256 `3ff558fd5389b1d0e67ec93676a79f9cb00f23823f0514bccf5591c90174f694`. It changes only PDESC and ResourceTransfer TFDT 0→4, retaining the one BASE-01 to `<OUTSIDE>` P-CREW quantity-one task at h6.
- Original prospective manifest: 445 records, SHA-256 `ce196b80f2365519885fb97b77eda0b04737736f239dfac46903df99edcf42a9`. Original contract SHA-256 `f03452c24030789f64a25df0419ffd574f97411a9ea0e1faa83df5743a22f793`.
- Original native closure SHA-256 `11905f40cd97487e542793453f52c30fcd3cbb0a46796665ec3eac1e2067007d`; invocation SHA-256 `6401b2f0a11b1ef35620adfd894b75729cc26bdd733ad68d36a6f915bddb712a`; failure seal SHA-256 `5f98f3161cdcf724608ce911b0a5dc0defd4cfdbc9a96180766b0d1a80ee2163`. Preserve all 26 original run files and their original paths.
- Formal original NO_GO memo SHA-256 `bf5701020822a59ea54324df9b6099987e49531b04110d64eec34347a20dc80a`. The original independent postrun reader failed before physical parsing on a missing catalog key; its 970-byte stderr is separately preserved. The later read-only diagnostic supports the raw comparison without accepting v1.0.0.

## Source and event states

The original child export retains TFDT 4 in the complete 32-table roundtrip. Parent and child logs each have 240 lines. The h6 OUT task 0 start prints transfer time 0 in the parent and 4 in the child. The parent task arrives at h6; the child task arrives at h10. Every other decoded log line matches in order. The v1.0.1 replay must bind the same task ID, P-CREW RID, route, quantity, and dispatch/arrival order in the original unedited logs.

At h6, one of two P-CREW leaves local BASE-01 in each arm. The child ledger has local one, in transfer one, completed outside zero on `[6,10)`; after h10 it has local one, in transfer zero, completed outside one. The parent has local one and completed outside one from h6. The direct reader must derive free/booked/nominal and both mission-wave intervals from source and typed events, reject a second decrement or backorder, and close the full ledger at h36. An equal local report is insufficient to prove the transit state.

## Report and process gates

The child and parent each have six report tables and 5,210 cells. Exactly one corresponding observed cell differs: authored ProblemDescription.PDESC. All other 5,209 corresponding cells match, including the five exact binary32 ResourceResultsTotal means (NR/NRA/NRN `1.1666666269302368`, NRUM `0.0555555559694767`, NRW `0.02777777798473835`). This is a crosscheck, while each expected cell must be reconstructed from source, typed intervals and predeclared bounded presentation conventions.

Four native stages and the roundtrip checker had captured integer exit zero in SSH session zero. The original behavior checker had captured integer exit one and `passed:false`, exactly because the frozen gate expected printed zero at h6. Preserve its stdout/stderr, checker JSON, invocation, closure and failure seal. Do not change that gate, rerun the native child, or reinterpret it as a passed prospective pair.

Installed manual pp478–479 describes OUT TFDT as ignored; this one installed executable/source row printed 4 and arrived at h10. The proposed classification is a bounded counterexample to the prior expectation in this fixed observation, without a general transfer rule or claims about IN, BETWEEN, other rows, GUI, performance or another engine.

Draft contract: `tmp/i03-var06-v101-retrospective-contract-draft-v5-20261008.json` (SHA-256 `66465e9a5df6c3e5a95f6b9b6b046bb6ea3b448a6512cb3e88ff7f2993f803dc`). Earlier v1, v2, v3 and v4 contract drafts remain preserved. This v5 draft supersedes an inherited historical h6-arrival assertion and requires the exact 491-entry catalog archive with a typed append-only live prefix; it is not an approved contract. The original input PDESC saying “ignored candidate” is retained as failed historical expectation, not revised evidence.

The in-transfer and completed-OUTSIDE counts are **derived task-linked quantities** from the observed departure and arrival. They are not observations of a stable person identity or an independently queried outside resource pool. Final publication will preserve byte-identical inert copies of the v100 non-run source/review history with exact original-to-copy mapping; the accepted parent/context raw and the failed v100 child run files remain mandatory at their original sealed paths.

The v5 draft additionally pins the original six SSH transport files and the seven files in each root preflight/native guard-and-transport directory. These originals remain distinct from any small owned custody copies in a later publication.
