# PR22 9e5020e default-GBK Windows retest

This is the new 4700-3 receipt for the explicit UTF-8 consumer/test repair at
PR22 `9e5020eeb0ea29a7e442a991e9f559b7e209d676`. It does not include PR22
engine code or change A01/A02 models. The previous default-GBK failure and
process-UTF-8 conditional pass remain unchanged in the versioned
[`5289fb5` receipt](../windows-retest-5289fb5-v1/receipt.json).

The machine-readable [receipt](receipt.json) cites immutable raw evidence under
`C:\Users\user\Documents\Codex\2026-09-27\simlox-pr22-default-gbk-retest-9e5020e-v1`.
Its `raw-artifact-manifest-v2.json` holds absolute retrieval paths, byte lengths,
and SHA-256 for 127 files. Exact command arguments, cwd, process selectors,
start/end times, exit status and raw stdout/stderr are in each `*-tests.json`,
`*-run.json`, `.stdout`, and `.stderr` record. All three output directories were
fresh and independent.

## Reproduce this bounded check

Use the supplied full-history PR22 bundle in a **new** detached checkout of the
exact head, retaining the real baseline Git object. For the ordinary checkout,
keep the machine's effective `core.autocrlf` setting. Use per-checkout
`core.autocrlf=false` and `true` for the separate LF and CRLF copies. The actual
commands were the existing Python 3.12.14 executable with:

```text
PYTHONPATH=src
PYTHONDONTWRITEBYTECODE=1
PYTHONUTF8 absent
PYTHONIOENCODING absent
python -m experiments.simlox_pairing.check_tests
python -m experiments.simlox_pairing.run --output <fresh-nonexistent-directory>
```

`driver.py` captures source identity before and after each command and refuses
existing record paths. `compare.py` checks the external native manifest pin,
historical receipt and raw 5289 evidence pins, actual consumer bytes against
independently supplied LF/CRLF pins, complete 25-JSON output membership and
every indexed byte hash. It then compares all nine case JSON objects to frozen
c97/5289 evidence, Plan and canonical bindings, four original native runs,
72 half-hour rows × five fields per case, full identities/event times,
integrals, terminal counts and four semantic negatives. It never starts SIMLOX.
`provenance_negatives.py` changes actual files only in disposable Git trees.

Each real outer Python process had `utf8_mode=0`, `locale.getencoding()=cp936`,
Python 3.12.14 and SimPy 4.1.1. Ordinary, controlled LF and controlled CRLF
each executed 35/35 tests with zero skips, failures or errors. The 32 tests
inside a modeled encoding regression are a separate nested check; they are not
the outer Windows acceptance. All three fresh A01/A02 runs passed 625/681
mapped checks, respectively. The result is a bounded A01/A02 mapping pass,
with no first discrepancy in the checked observables.

GUI calibration/review still awaits private user handoff. Engine notification
remains a commission-time proxy; the native inner task is unmapped. This receipt
does not establish fault, resource, spare, cancellation, J35/F35, RNG, or
performance equivalence. No native SIMLOX, GUI, or benchmark process ran here.
