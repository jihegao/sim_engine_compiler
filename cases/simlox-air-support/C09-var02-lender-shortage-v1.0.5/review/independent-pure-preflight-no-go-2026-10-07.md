# Independent exact-file pure-preflight review — NO_GO_PURE_PREFLIGHT

Decision: **NO_GO_PURE_PREFLIGHT** for `c09-var02-v105-shortage-ssh-20261007-01`. No actual SSH preflight or native child was invoked by this review. No `independent-prelaunch-go.json` is issued.

## Frozen identities checked

| File | Bytes | SHA-256 |
|---|---:|---|
| `contract.json` | 22,919 | `faf40af730062c6a2415e207cac9833e6534b03225d820f9e02e7f070b4f1d4e` |
| `prelaunch-manifest.json` | 132,674 | `f16251fc6eff445a48a30fc7632c85a0dc609639f8f7212980c393b88a1dbbed` |
| `run_native_ssh.ps1` | 15,775 | `0964f939322dfcec893e5f62d2012484893216820e9ae6f55a76fd776f16c779` |
| `validate_native_cli.py` | 11,239 | `f49f18999dd6393f0ca1027fda2133591d1ac12eee45894314e7bd0476811836` |
| `verify_sources.py` | 7,291 | `5778fe984b5392e5f2d50a31686e059bac5058130bfbb49dd9a53eb8ef07445c` |
| `physical_ledger.py` | 8,664 | `e646ed91f36dee65853ee1ed62a82fe9354c6e220ae5fa58a37a6538b8b6d66f` |

The independent manifest pass compared all 384 source records to local file sizes and SHA-256 values, with zero mismatches. That confirms the reviewed source is the frozen bundle; it does not establish behavioral acceptance. The reviewer-owned `review/independent_replay.py` remains an unapproved candidate and is not a native approval artifact.

## Blocking contract mismatch

The frozen contract's `predeclared_event_gate.home_after_return` requires that **additional later trips or PM cycles be parsed, identity-matched, and fully reconciled**, with NO_GO if they prevent isolation of the intended matched return. `return_branch` applies the 0.125 h requirement to that matched return task. It does not require a single lifetime PM/repair cycle or a 0.125 h duration for every unrelated later return.

Frozen `physical_ledger.py` rejects those permitted traces before full reconciliation:

1. Lines 69–71 assert `transportation time: 0.125` on **every** child return task, although lines 97–105 separately isolate one shortage-attributed return and lines 100–102 already test its duration. A later return under another route would fail the global check even if the matched return is exactly 0.125 h.
2. The `one()` helper at lines 14–17 requires exactly one match. Its calls at lines 19–39 and 107–111 apply that global uniqueness to HOME PM start/PMID/completion, HOME wait edges, borrower repair release, and HOME mechanic booking/deallocation. A second fully linked later PM or repair cycle would fail on count alone rather than being reconciled by task and cycle ID.

The accepted ordinary control happens to have one qualifying cycle, so its self-check cannot exercise these false-negative cases. The prospective child has not run. A lone-cycle synthetic child likewise cannot prove the contract's additional-cycle branch. This gap is material for a sole native attempt: a valid contract-compliant child could be sealed as failed by the checker.

## Recovery gate

Preserve this frozen v1.0.5 bundle and review. Use a new contract/version and unique run ID. The corrected physical checker must identify the matched shortage-attributed return by transport/task/station/request edges and apply 0.125 h only to that return; it must group later trips, PM tasks, waits, bookings, releases, and completions by identity and reconcile all event edges, quantities, station occupancy, and full reports. Include pure in-memory negative controls for an ambiguous or unlinked extra cycle, and a positive contract-permitted linked later cycle. Obtain a new exact-file static review before actual SSH5 `-PreflightOnly`, then separate prelaunch approval. No approval transfers from this version.

This is a static source/contract decision. It does not claim that additional cycles occurred, that the prospective TTRSS branch was observed, or that the child satisfies any of the 1,754 report-cell gates.
