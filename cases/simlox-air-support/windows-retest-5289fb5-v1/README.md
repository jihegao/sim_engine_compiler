# PR22 5289fb5 real Windows retest

This is a bounded, read-only A01/A02 pairing review on 4700-3. It records the
actual source bytes and an ordinary Windows checkout before tests, separate LF
and CRLF checkouts, fresh consumer executions, mutation controls, and comparison
against four sealed native SIMLOX runs. The machine-readable verdict is in
[`receipt.json`](receipt.json). The immutable command logs and output files are
indexed by absolute path and SHA-256 in the task dispatch's
`raw-artifact-manifest.json`:
`C:\Users\user\Documents\Codex\2026-09-27\simlox-pr22-windows-retest-5289fb5-v1`.

The supplied PR22 bundle was verified and checked out detached in that dispatch.
The native branch does not contain PR22 source. The ordinary checkout inherited
system `core.autocrlf=true`, giving 26 strict whole-file CRLF source files. Its
portable build fingerprint is the frozen baseline blob fingerprint; its executed
byte fingerprint records the actual CRLF bytes. A separate LF checkout used exact
Git blob bytes. A separate CRLF checkout reproduced the ordinary mode.

## Recheck commands

Use the existing Python 3.12 environment. Set process-local `PYTHONPATH=src`,
`PYTHONDONTWRITEBYTECODE=1`, and `PYTHONUTF8=1` before running in each isolated
PR22 checkout. From each checkout:

```text
python -m experiments.simlox_pairing.check_tests
python -m experiments.simlox_pairing.run --output <fresh-nonexistent-directory>
```

The retained exact commands, environment selectors, start/end times, exit codes,
stdout, and stderr are in the dispatch's `*-tests.json`, `*-run.json`, `.stdout`,
and `.stderr` files. `driver.py` records new runs and refuses existing record
paths. `compare.py` verifies fresh parsed engine results, 72 half-hour profile
rows per case, stable aircraft and mission identities and event times against
both the frozen c97 result and each original native normal/replay run. It does
not start SIMLOX. `provenance_negatives.py` tests actual disposable source
mutations; its final record is `provenance-negatives-v2.json`.

The untouched ordinary checkout's first 32-test command without `PYTHONUTF8`
had 31 passes and one test-harness error: `Path.read_text()` decoded an emitted
UTF-8 JSON file using the Windows GBK locale. The unchanged checkout with
process-local `PYTHONUTF8=1` passed all 32 tests with zero skips. Both controlled
checkouts also passed 32/32 under that selector. This locale issue is separate
from the repaired source-provenance check; the unconfigured failure is retained.

This receipt verifies only the A01/A02 teaching-case mapping. SIMLOX GUI review
still awaits private user handoff. Commission-time `preflight_created` is a
notification proxy, `mission_ready` is mission bound, the native inner task is
unmapped, and no stochastic, fault, resource, spare, cancellation, J35, F35,
performance, or full cross-engine equivalence conclusion follows.
