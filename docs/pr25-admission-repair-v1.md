# PR #25 admission and publication repair

The Ready-for-review checks on `9737822` identified two harness defects:

- Four duplicate-seed samples cap the nominal eight-worker gate at four
  effective workers. The original measured window has a separate actual-eight-
  worker supplement, but the reusable command did not enforce that admission.
- `summarize` checked the frozen manifest and measurement records without
  revalidating the sealed semantic gate and its raw files.

The Rust CLI and public PyO3 gates now use eight samples (`[7, 0, 7, 1] * 2`)
for the one/eight-worker Full/Summary comparisons. Both validate the returned
effective worker count. Summary generation calls `validate_gate_evidence`
before reading measurement records or publishing any completion claim.

The 28 bounded controls include executable Rust/PyO3 orchestration checks,
rejection of a four-worker result requested as eight, and rejection at summary
time of missing gate evidence, missing seals, changed manifest binding,
changed raw results and enabled candidate dispatch. These are synthetic
harness controls, not a new F35 or performance run. The placement control now
explicitly creates its mocked Linux affinity function on macOS too; production
placement validation remains unchanged.

## Historical evidence

All files in `benchmarks/cpu_batch_v1/results/amd128-20260927/`, including the
raw archive, remain byte-for-byte unchanged. The original frozen protocol,
driver identities, 21 gate checks and separate actual-eight-worker supplement
retain their historical scope. They do not claim execution with this repaired
driver. Inspect or reproduce historical evidence using its frozen source
revision; a new run with the repaired driver requires a new manifest and its
own semantic admission. This repair does not open another measurement window,
change engine behavior, or complete Issue #6's J35 three-arm/IR-reuse work.

Validation: all 28 bounded controls execute without skips locally. The dedicated
Linux controls and complete integration CI must pass at the repair commit
before merge; their exact-head results are recorded in the PR review replies.
