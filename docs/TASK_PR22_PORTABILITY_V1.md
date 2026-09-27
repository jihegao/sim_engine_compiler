# Active task / resume here

Task `engine-review-data-recovery-and-pr22-portability-v1`, part A, 2026-09-27.
Authority: coordination thread `01a0df64-5e20-7d61-88f1-cf3be014e781`.
Worktree `/home/g/apps/sim-engine-a01-a02-pairing`, existing PR22 branch
`codex/a01-a02-engine-pairing-v1`, starting commit
`c97b73241ef961b99c2c416488bdd6462ce0e1d2`.

Repair consumer provenance only: canonical POSIX path keys and an explicit
Git-blob versus executed-working-file byte policy. Reproduce Windows path and
CRLF failures; never trust HEAD alone, drop the fingerprint gate, skip tests,
or ignore dirty runtime sources. No global Git config/bulk conversion/runtime
or RNG semantics changes. Preserve old evidence files and Windows failure
history. Old native receipt is PR21@2c0277b42586a6c02af18152d2cdc0806073c953,
receipt SHA256 330c968bb26e7c6c1be83d3b3007221f05b32d09578634932e972b22718815c4.
Reported Windows old tests: 24 passed, 2 source_identity errors, 0 skipped.
POSIX source aggregate 8b029a0a79495bbdadb7f133ff035eb19c564365fe1c6315b3ba56289496ded1;
backslash keys produce a20bb50e2db1c557351edfa52ca8f690a5529c4bcd50e8e59c3d62a2b77c579f.

Test POSIX/Windows paths, newline policy, actual content/dirty file mutations,
identity/Plan mismatches. Preserve 4 pairing negative classes, 72 bins and
625/681 finite checks. Update existing PR22, exact-head Linux CI and independent
review. Actual Windows/4700-3/SIMLOX work belongs only to its coordinating chat;
do not execute it here. Delivered/rebuilt ZIPs are not byte identical: coordinator
reports 24 central-directory create_system bytes differ with equal member data
and compressed streams. Do not rewrite historical receipts.

Stage: implementation and 32-test no-skip local pairing validation complete;
independent review and exact-head Linux CI are the current gates. The frozen
repair separates baseline blob/working-file bytes with strict CRLF policy;
old v1 evidence unchanged. CI fetches the exact baseline object explicitly.
Do not claim native Windows reacceptance. Final CI/commit handoff belongs in PR22.
Separate issue10 implementation lives in
`/home/g/apps/sim-engine-review-data-v1`; no mixing PRs, automatic merge, native
SIMLOX, performance or paid pilot. CSABench commit 2b5acbb is preserved only.
