# Independent staged publication review — C06.var01

Decision: **GO_STAGED** for the bounded read-only C06.var01 publication snapshot on branch `codex/simlox-c06-var01-primary-availability-20261007`. This memo is untracked and excluded from the self-sealed evidence index.

The staged change has exactly 13 intended paths: 12 files under `C06-var01-primary-availability-v0.1.0` and one append to `publication-index-v1.json`. There are no staged run artifacts, product-runtime edits, or unrelated paths. All 11 new evidence-index source SHA-256/size pins match both working bytes and staged Git blobs. The evidence-index SHA-256 is `a481711c2a8ea4ccb297aa6bb40206763da3db78b0bafb216211e2ce40833afa`. Separate local and published Git byte identities match for all 17 accepted C06 and 16 C03 source files. The accepted C03 parent invocation/closure and 11 raw files, and both C06 invocations/closures and 24 raw files, match their SHA-256/size records. The core.whitespace=cr-at-eol staged diff check is clean.

The staged root index parses to 480 unique publication IDs. Its first 479 entries and non-entry metadata equal `origin/simlox/main`; the new 480th entry identifies the case, signoff, evidence index, no-new-native classification, exact primary-crew 2→0 source contrast, typed resource timing, six-report changed-cell counts 1/0/13/0/218/4, and the limits. The signoff and README cite author `GO_BOUNDED` 13,313/13,313 and independent `GO_BOUNDED` 14,192/14,192, matching the pinned verdicts. They disclose that ARTF is fixed at two, the behavior is already in accepted C06 evidence, and no general fallback law or full Issue18 result follows.

This is approval of these staged bytes and their bounded claim. It is not a fresh SIMLOX execution or a remote PR/CI review.
