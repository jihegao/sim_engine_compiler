# Active task: resume here before implementation

Task `engine-trace-query-issue11-1a1e329-v1`, authority coordination thread
`01a0df64-5e20-7d61-88f1-cf3be014e781`, dispatched 2026-09-27.
Worktree `/home/g/apps/sim-engine-trace-query-v1`, branch `codex/trace-query-v1`.
Exact parent PR23 `1a1e329ca4e7c38a7550ac9de15c699fccfb99ef`; stacked PR base
`codex/review-data-v1`. PR23 depends on unmerged PR20
`c42d2679c6652a3f5e2d43c9ddc877ee5a388656`. No merge/rebase/issue closure.

After compaction, reread this file, AGENTS and required README/architecture/
semantic-baseline/roadmap, then current implementation/status. This is always
sim_engine_compiler, not the initial CSABench cwd. Preserve CSABench 2b5acbb.
PR22 real Windows recheck belongs to the unique 4700-3 coordinator; do not
operate Windows/native SIMLOX or change its historical evidence.

## Authorized slice

Offline package API/CLI for existing independently persisted Full/Summary
result/run plus request and optional raw Business/Core/Plan/lineage bundle.
Reuse public identity and review mapping authority, never trust a supplied
inspection report or self-reported hash as association proof. Declare run/sample,
Plan/profile/seed/parameters/observation/cutoff identities. Duplicate seeds are
allowed, samples remain separate. Original event sequence IDs survive all filters.

Bounded filters: run/sample, entity/process, time window, event/rule IDs; stable
selected/omitted/partial diagnostics, pagination and offline output budgets.
Budgets are NOT runtime collection budgets. Files, results, metrics, terminal
state, ledgers and original trace remain unchanged.

Expose only recorded rule/source/process/entity/details facts with explicit
categories; link design nodes only using a validated matching raw bundle.
No temporal adjacency as causation, unrecorded candidates/guards/state inferred,
extra random draws or fabricated triggering references. Missing cache/candidate/
resource/inventory/cancellation evidence stays unknown/insufficient.

Controls must cover Summary, legacy/missing trace, deleted/reordered/duplicate
sequence, absent lineage, mixed revision/wrong Plan, omitted reference targets,
inclusive/exclusive window endpoints, pages and insufficient output budget.
Declare inability to detect unsigned continuous tail deletion. Unknown backend,
profile and event types must be rejected or explicitly capability-limited.

## Exit gates

- Versioned API/CLI query/diagnostic contract, support matrix and offline #10 link
  example; source evidence separated from generated output.
- Real hand-calculable B1/B3 recorded waits/cancellations or explicit insufficiency.
- F35 seeds 0/1/7, applicable Full/Summary/profile variants: source artifacts and
  complete result hashes unchanged across queries. No legacy semantic repair.
- Python offline queries are NOT Rust collection acceptance. Either finite real
  Rust results are field-scoped tested or support explicitly unverified/rejected.
- Independent adversarial review (false causality, cross-run links, stale revisions,
  missing-evidence honesty), all new modules collected/executed without CI skips,
  preserve Rust/PyO3/mandatory MLIR gates and report exact-head CI.

No runtime instrumentation/guard hooks/default trace policy/scheduling changes,
performance or collection-overhead experiments, UI/service/JIT/distributed work,
paid pilot, 1000-sample/native SIMLOX or full #11 acceptance. Any necessary minimal
identity/review contract repair must be explicitly scoped; never business semantics.

Stage: implementation and four test modules complete; independent review and
exact-head CI are the exit gate. Public contract is docs/trace-query-v1.md.
Main owns query admission/filter/pagination/CLI/docs/CI; separate workers own
facts/design-link projection, behavioral/negative tests and independent review.
Python reference minute Full is the supported collector. Rust and O5 are
explicitly unsupported; Summary is evidence insufficiency, not collection
acceptance. Independent review caught missing result Plan identity authorizing
stale design links; fixed with a recorded-Plan-fingerprint gate and B1/F35
cross-revision negative controls. Record final head/PR/CI in the corresponding
PR and ignored runs/trace-query-v1/handoff.json. No merge or issue closure.
