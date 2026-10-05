# Issue 18 monitor112: independent static E05.var01 prelaunch review

Reviewed 2026-10-05, heartbeat trigger 14:03:07.869Z; reviewer is the existing Mac mini monitor (not the case author). Native executor stays 4700-3 original chat 01a0ed5b-dc75-74f3-a26c-23674dd997d6. Scope: read-only current package, source/AST inspection and accepted E05/E02 raw controls; no author checker import/execution, no native attempt, no behavioral test, no parent rerun.

## Verdict: NO_GO_PRELAUNCH

The provider-capacity failures returned no runner verdict. This review supplies concrete source findings; it does not waive independent review or issue a native behavior acceptance. Preserve the current bytes and both reviewer capacity failures. Do not start the child or publish this candidate until the findings are repaired and the complete new package receives fresh independent GO.

Reviewed exact current package:
- input 5d91b1315d1a3d6321285492e8fcd4a3afd61bc8420347713f5646c31cfe5d08
- contract 69929e2efb3913aff4e73f8a6524e9fd4af792653ebf66fe3ab285c9ea594375
- runner ebaae05c1b3c2e57cacbb1e85f1a400c9f2ad3d4c2eb8b9b731947f3a5fa5cf3
- validator aa61ae4fb4bda80677c1842cabb626bd7500b39c9ed5da3c2751f0ebb703acac
- prelaunch status 28e1e24e91be774c5ca2adf593350e2d3cb52dff7b2fae0cf6ede3b36f8cb9b9

Repo AGENTS.md, README.md, docs/architecture.md, docs/semantic-baseline.md, docs/roadmap.md and execution-plan-v2.md were read before this review. Keep all three IR layers and separate RunState; these proposed repairs belong to case acceptance tooling, not generic runtime model dispatch. The child source remains one DIRPT cell 1 -> 13; all 12 accepted E05 parent raw seals and parent input/signoff/closure pins match. No E05.var01 runs directory exists in the captured package.

## F1 — blocking: declared physical task/wait/terminal assertions absent

validate_native.py lines108-162 collects stock events, demand failed-item IDs, repair starts/finishes and generic SURP receipts. It never collects remove/fit subtask start/completion, SURP completion or system terminal state. The parsed printed backorder wait at line112 is never checked against addition/removal times. The first-repair bridge predicate at lines132-134 checks temporal containment plus an eventual matching received item; it does not bind that repair-return receipt to the specific backordered demand, failed physical item, removal and fit task. Terminal on-hand cardinality in line162 does not enumerate pending repairs or justify which start should remain unfinished at hour36.

Contract native_gate[3]/[4] requires every observed demand and physical LRU through removal, direct repair, return, installation and terminal state, including unfinished repair and wait/fit times. Add an identity/task-linked ledger with exact sequencing and justified printed-time tolerances; verify removal duration 10min, actual fit start/wait and fit completion duration20min, system SURP completion/availability, each completed13h repair and each legitimately pending repair at horizon. Match each backorder add/remove/printed wait to its demand and replacement receipt, or explicitly fail unsupported ambiguous matching. Do not import parent's observed failure/demand times as this child's expected times.

The accepted E05 raw control contains remove/fit/SURP completions. The accepted E02 zero-stock control contains fit waiting, printed wait1.16667, same-time repaired-item receipt and later fit/SURP completion; these controls establish parsable event forms without rerunning them. A parser matching E02 backorder strings alone does not prove this full chain.

## F2 — blocking: report metrics are substantially unchecked

At lines164-181 both required tables are decoded, but AST/source inspection shows only row fields STINT/ETINT/NBO/NDF are read. SystemResults values other than interval endpoints are never checked. StockTotalResults checks only whole-horizon NBO*0.5 and totalNDF; opposite per-bin errors could cancel. This is weaker than contract's 72-bin report/event reconciliation and system/terminal behavior claims.

Derive interval overlap and demand membership independently from the physical task/availability/backorder ledger, reconcile relevant documented fields for each of all72 rows (including identities/row cardinality, horizon boundaries and terminal unfinished work), and preserve raw report bytes. Treat StockTotalResults as aggregate; never infer physical IDs/on-hand transitions solely from it. If a field's native meaning cannot be established, retain an explicit unverified restriction and get a revised contract review, rather than claiming complete metrics acceptance.

## F3 — source binding gap

source_paths at lines74-83 omits author_validator. The checker never compares contract.author_validator_sha256 against its own current bytes or invocation.source_hashes_before.author_validator. Runner seals validator but not the shared tools/validate_native.py module imported on line17; the latter supplies report normalization and roundtrip comparison semantics.

Bind the exact current validator bytes to contract/invocation/closure and preserve before/after checks for the shared imported dependency (or freeze a separately pinned dependency manifest). Recompute literal contract/validator/runner pins and fresh prelaunch status when repairing; retain this reviewed snapshot as diagnostic evidence. No native attempt exists yet, so no run directory may be reused or synthesized. Any future started run must have a unique frozen version/run ID and preserve failures.

## Safeguards inspected, not a GO

Current runner uses SSHsession0/sshd ancestry, Global\SimloxIssue18NativeQueue, protected GUI PID/session/start/response, exact20-table roundtrip before calculation, child-only PID/session/commandline watchdog, defaultreport and raw/failure closure. These are positive code observations, not actual host launch proof or comprehensive verified safety. Immediately before any later approved launch, recheck live owner, package hashes, vacantrunpath, GUI identity, SSH and queue.

## Next step to original executor

Read this independent review, preserve old package/check evidence, repair F1/F2/F3 in the existing E05 case workspace and perform related authorized static/negative checks. Obtain fresh independent GO on all changed package bytes before native launch. If review capacity or a repair stays blocked, retain E05 and its recovery condition, then choose other eligible unoccupied planned work with parent behavioral scope/dependencies satisfied. Do not repeatedly request the same unavailable reviewer in this turn. Do not alter model or formal Goal status, create a replacement chat or a second executor, rerun accepted parents, retry known GUI capture helpers, or call the overall Goal complete.
