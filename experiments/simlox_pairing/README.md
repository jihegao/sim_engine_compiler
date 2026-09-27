# A01/A02 bounded engine pairing v1

Task: `engine-a01-a02-pairing-519b209-v1` (2026-09-27).
Engine semantic baseline: `main@595cb5eee9987324b19a8c3566f201f937e05f15`.
No compiler, Plan, Python/Rust runtime, RNG or business semantics were changed.
This experiment neither uses nor merges the unmerged PR #20 identity API.

## Outcome and acceptance scope

Both independently executed teaching cases match the frozen **mapped**
observables: A01 625 checks, A02 681 checks, with no first discrepancy. Every
case has 72 half-hour bins checked field by field, plus mapped identities/event
times, cumulative quantities and terminal counts. These are deterministic
checks, not independent statistical samples or an accuracy score.

| Case | Notice/binding; launch; completion (hours) | FTMO / NSYMO / NSYMA / NSYMR / NSYRY integrals | Completed waves |
|---|---|---|---|
| A01 | 7; 8; 10 | 2 / 2 / 3 / 1 / 33 | 1 |
| A02 | 7/19/31; 8/20/32; 10/22/34 | 6 / 6 / 9 / 3 / 27 | 3 |

FTMO integrates to hours; NSY fields integrate to aircraft-hours. The native
report is total-over-units/systems; it equals the single aircraft here only.
Units and field-level tolerances come from the externally pinned manifest.

The machine-readable [consumer report](evidence/v1/consumer-report.json)
instantiates the supplied template. Each case directory retains independently
produced canonical input, Business/Core/Plan, lineage, source mapping, raw engine
result, extracted observation and every comparison check. File hashes and
[source/build fingerprints](evidence/v1/source-fingerprints.json) are separate
from the immutable native dependency. `commit` in that identity means the engine
source baseline, not the later consumer PR head; the actual consumer source files
have their own fingerprint. The CI run binds the exact PR head separately.

## Reproduce

Python 3.12, SimPy 4.1.1, existing package test extra (pytest 8.4.2):

```sh
uv venv --python 3.12 .venv
uv pip install --python .venv/bin/python -e '.[test]'
PYTHONPATH=src .venv/bin/python -m experiments.simlox_pairing.check_tests
PYTHONPATH=src .venv/bin/python -m experiments.simlox_pairing.run --output /absolute/fresh/output
```

The output directory must not already exist. No native executable, database,
Windows filesystem, web service or network access is needed at execution time.
The dedicated CI runs all four named test modules, requires each to contain
actual unittest cases, rejects skips/expected failures and reconciles collected
and executed counts. The existing full Rust/PyO3/mandatory MLIR workflow is
unchanged. Local optional-MLIR skips are not acceptance for that remote gate.

## Source and modeling boundary

The exact PR #21 dependency `519b2094c3be355399bc101cdcfe30d456cbb47b` was fetched
from GitHub in a separate read-only checkout. Its accepted native source is
`04dce604f6be75df064d40519187b482ceb4ddb8`. See the
[snapshot provenance](../../tests/fixtures/simlox_pairing/README.md): the external
manifest and every payload byte were verified with `portable.py verify`.
The locally rebuilt ZIP differs from the delivery ZIP hash; the original ZIP's
bytes were not available and are not claimed as verified. Original Windows raw
evidence paths remain untouched references. Native execution and GUI review are
not repeated or newly accepted here.

`canonical.py` constructs explicit self-authored `simulation_inputs`, not a
Project JSON or SIMLOX interpreter. The actual upstream schema at
`spare_mvp@5352a0d7757cbac012c75d516d1a7ac4ff15aa2a` was read using `git show`;
its SHA-256 is
`bd8d6acca8e4fb678bf0b536d257fae41811f44e3c841b13cabdc32c2fe3f694`.
Both inputs were checked against that schema. Production compilation uses the
existing `integrations/spare_mvp.import_business_ir -> lower_business ->
compile_core -> SimpyReferenceRuntime` chain, without upstream model execution.
Native expected observations are loaded only for validation, never supplied to
the engine producer.

All preflight/relaunch/postflight activities have **empty steps**: there is no
invented one-hour preparation work. `advanceNoticeMinutes=60` starts the existing
zero-work binding lifecycle. `mission_ready` means ready for the assigned
mission, not globally available; the observer counts it as reserved/not ready.
A02's third engine mission is on engine day 2; its native ordinal mapping is
explicit rather than pretending native day/index fields are interchangeable.

## Observation limits and rejected counterexamples

Notification is a `preflight_created` commission-time **proxy**, not an
independently captured notification event. Allocation/ready loss derive from
the actual aircraft-to-mission binding; launch and return are recorded runtime
events. Initial readiness comes from the Plan's initial state, not an invented
trace event. No claim is made about equal-time native/engine emission order.
Native creation/activation, inner tasks at 8.5–9.5 hours (and later waves), and
zero-time preparation log markers remain native-only. NPSTA=0 is not a modeled
preparation activity. Thus the report says
`matched_mapped_observables_not_full_equivalence`, not full model equivalence.

The [negative controls](evidence/v1/negative-controls.json) retain a genuinely
recompiled/re-executed half-hour-shifted input, Plan and raw result. All four
controls were detected:

- Same cumulative quantities and terminal counts, wrong schedule: first event
  time discrepancy 450 versus 420 minutes; first state-bin discrepancy
  `intervals[14].NSYMA` (0 versus 1).
- Wrong aircraft identity at unchanged times/totals: identity comparison fails.
- Wrong result/Plan fingerprint: extraction rejects before projection.
- Wrong canonical-input/Plan binding: comparison fails before profile checks.

Separate tests reject duplicate identities, unknown trace kinds/profiles,
tampered terminal state, archive tampering and silent zero-test discovery.
The observer deliberately rejects unsupported mechanisms instead of dropping
them. No baseline implementation defect was found or repaired in this slice.

SIMPE=36h is the simulation endpoint; RCEND is a separate statistics window.
MSUF=1 at RCEND=9h is not a completed mission count. Conversion rejection #204
is not dynamic cancellation. This work does not establish faults, resources,
spares, cancellation, same-time priority, shared RNG streams, complete F35/J35
equivalence, GUI acceptance, A03 support or any speedup. No formal timing, native
SIMLOX execution or paid pilot dispatch occurred.
