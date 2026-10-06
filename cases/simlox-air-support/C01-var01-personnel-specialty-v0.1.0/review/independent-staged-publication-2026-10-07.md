# C01.var01 staged publication review — 2026-10-07

**Decision: GO_STAGED**, for the bounded read-only C01.var01 classification. This reviews the current staged snapshot; this memo remains untracked and is outside the self-sealed evidence index.

- The stage contains exactly 13 intended paths: 12 under `C01-var01-personnel-specialty-v0.1.0` and the root `publication-index-v1.json`. It contains no run blobs, native executable, product source, or unrelated path. `git -c core.whitespace=cr-at-eol diff --cached --check` passes.
- The new evidence index SHA-256 is `8ae8e3afd3fb48ec9e3ea697b21576a3a5fa3dbc3d562a35fa6ebb6c8b91e04f`. All 11 indexed source SHA/size records match both worktree bytes and staged Git blobs. Its signoff and review links resolve.
- The accepted C01 index's 18 source identities match local and published `origin/simlox/main` Git bytes. Its `.gitignore` is correctly dual-pinned: local CRLF eight-byte SHA-256 `8d22814e19ac1121bcdcfb89aa88c9da384ec98d2f31f90cedc7a29f95b5f17f`, published LF seven-byte SHA-256 `127672b43b817aa8f10c44cdb48d4eeef8c0201da894e8a2430cce505ab49933`.
- The original qualified and wrong-specialty closures retain SHA-256 `770537c9097ba24fbec533d5c6f1eafa29153c18bde63cd0b1bc621a65c55163` and `610b2b9d12352a9ca06f9241c2d20f824bfa759fffd0a6f202d2ee1b4a44ba8f`. All 22 original raw SHA/size seals match their unchanged local files.
- The staged author verdict says 147/147, and the independent verdict SHA-256 `1d5670ba64b77fed778a13aaac726c71fc83c2c792d3b75658d9da90fbdb2801` says 11,079/11,079, including 5,210 report cells per arm. README and signoff accurately state the two `ResourceAllocation.RQTY` differences, equal total capacity two, the observed booking/work/mission contrast, no new native run, and the fixed-seed, exact-resource-ID limit.
- The root publication index retains its first 469 entries and other metadata unchanged and appends one unique bounded 470th entry, `C01.var01.personnel_specialty.0.1.0`. It makes no general specialty, partial-booking, GUI, or full Issue #18 claim.

This verdict covers staged content and local reused raw evidence. It does not assert remote PR bytes, CI success, or behavior beyond the two accepted runs.
