# C03.var01 v0.1.1 staged publication review — 2026-10-07

**Decision: NO_GO_STAGED for the current staged snapshot.** The cryptographic evidence and scoped publication entry pass. The staged signoff still describes source-byte sealing as pending, although its own evidence index is already staged. Correct the signoff wording, regenerate its source pin in the evidence index, and restage before a fresh publication review. This memo is untracked and outside the frozen evidence index.

## Passing evidence

- Exactly 15 paths are staged: two preserved v0.1.0 contract/NO_GO files, 12 v0.1.1 package files (11 indexed sources plus `evidence-index.json`), and one root `publication-index-v1.json`. There are no staged raw runs, product runtime files or unrelated paths. `git diff --cached --check` passes.
- Evidence index SHA-256 `c73c730cefc2489b6997aa5af388191687efea7e6967947f257aa7df7627a573` matches the staged/disk file. All 11 new source and two excluded-source byte sizes and SHA-256 values match **both** worktree and staged Git blobs. All 16 accepted C03 source records match local and published Git identities, including the stated `.gitignore` CRLF/LF distinction. The three final closure/invocation records and all 33 raw SHA/size seals match. Total checked index records: 68; mismatches: zero.
- Author verdict is GO_BOUNDED 16,955/16,955 and separately authored independent verdict is GO_BOUNDED 18,091/18,091. The README and signoff's physical 2/1/0 capacity observations and fixed-seed limits agree with the accepted raw replay. README relative links resolve.
- The root index has 473 distinct publication IDs. Its first 472 entries and metadata equal the prior committed index; the sole new C03.var01 entry describes the bounded read-only three-run comparison. Its staged Git bytes use LF and differ from the CRLF worktree bytes, but parsed JSON is identical; this is not an evidence-index source byte pin.

## Required correction

`cli-scope-signoff-2026-10-07.md` opens with “source-byte index and independent publication review pending” and later states “Source-byte sealing and independent publication review remain required.” The source-byte index already exists and is staged. At least the source-byte sealing status should be updated before publication. Keep the independent publication review conditional until the corrected stage is audited. The signoff is an indexed source, so changing it requires an evidence-index regeneration and new SHA.

No native or GUI process was invoked; no staged, accepted, or raw file was edited.
