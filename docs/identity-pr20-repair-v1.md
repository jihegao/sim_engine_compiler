# PR #20: test discovery and event evidence repair

Task: `engine-identity-pr20-repair-7758554-v1`, 2026-09-27.
Repair parent: `7758554756ade5b91c42b149673c01751592e90d`.
PR base: `595cb5eee9987324b19a8c3566f201f937e05f15`.

## Reproduced defects

- [CI 36277878129](https://github.com/jihegao/sim_engine_compiler/actions/runs/36277878129)
  ran unittest discovery without pytest: 172 tests, four import errors, and
  function-style tests were not discovered. Installing pytest alone would not
  have fixed the silent omission.
- [Horizon review](https://github.com/jihegao/sim_engine_compiler/pull/20#discussion_r4113218575):
  a request horizon of zero could accept a result/event at time 100 as complete.
- [Sequence review](https://github.com/jihegao/sim_engine_compiler/pull/20#discussion_r4113218586):
  sequences `[1, 8]` or `[8, 1]` could be labelled complete.

Independent reproduction confirmed both evidence defects before repair.

## Repair and controls

The workflow installs the existing pinned `.[test]` extra, collects and executes
the full `tests` tree with pytest, and reconciles every collected node ID with
JUnit execution evidence. Each of the seven identity modules and the verifier's
own control module is mandatory and cannot be skipped. Collection, JUnit,
execution logs and machine-readable counts are uploaded with the existing
acceptance artifact. Rust runtime/AOT/cache, PyO3 and mandatory no-skip MLIR
steps are retained unchanged.

The offline event projector and resolver now enforce temporal bounds and
sequence completeness as documented in [the contract](identity-contract-v1.md).
Focused controls cover zero horizon, boundary times, earlier natural completion,
actual B1 reference output, malformed/missing time, out-of-range filtered events,
gaps, reordered input, stable IDs, and rehashed false completeness claims.
No Plan, runtime, RNG, compiler lowering or business semantics are changed.

## Acceptance evidence

Final local tree: Python 3.12.13, pytest 8.4.2, SimPy 4.1.1.
`pytest tests` collected and recorded 279 cases: 265 passed, 14 optional
integration-environment skips, zero failures/errors (94.93 seconds). The
collection/JUnit verifier passed with identity module counts
14/6/16/2/41/27/15 (121 total) and five verifier controls. The nine separate
`experiments/ir_validation/test_review_fixes.py` controls also passed. Focused
identity plus verifier execution passed all 126 cases. Ruff and diff checks
passed. These overlap, so they must not be summed as independent samples.

The repair review receipt is `identity-pr20-repair-review-v1.json`; it binds
the final reviewed files by hash, separately from the historical initial review.
Local results and remote CI must be reported separately. Local optional-MLIR
skips never count as required MLIR acceptance. The repair commit's own GitHub
Actions run is the authority for the mandatory integration gate; its head SHA,
test counts and URL must be read back before handoff. No older successful run
is substituted for this gate.

This repair does not merge PR #20 or any other PR, authorize formal timing,
run SIMLOX native tests, or authorize paid pilot dispatch.
