# Portable A01/A02 pairing handoff

This archive is a small, self-authored teaching contract for one generic
aircraft. It is not a real F35/J35 model, an Execution Plan, or a second
`spare_mvp` Project interpreter. Accepted source commit:
`04dce604f6be75df064d40519187b482ceb4ddb8` (Draft PR #21, CI
36277892011). The four SIMLOX CLI normal/replay runs are already accepted on
4700-3; the archive includes their compact indexes and SHA-256 references,
not proprietary SXI/SXO, complete reports or ENLOG files.

## Verify and consume

Use Python 3.12+ standard library only. After extracting the archive, or with
the archive intact, run:

```text
python portable.py verify --zip a01-a02-pairing-v1.zip --manifest-sha256 <SHA from external delivery.json>
```

The manifest and delivery metadata are separate to avoid a self-hash cycle.
The portable verifier checks exact package membership, per-file hashes,
accepted source/input/contract fingerprints, units, identities, all 72
half-hour state rows per case, event lifecycle, terminal counts, RCEND
classification and the engine-not-run report template. It uses no Windows
path equality and does not execute or validate SIMLOX raw evidence.
`consumer-report-template.json` is the minimum AMD128 return format; its
engine and equivalence statuses intentionally start `not_run`/`unverified`.

For a fresh original-evidence check on **4700-3 only**, from the accepted
checkout use the existing isolated Python and case-specific command:

```text
python cases/simlox-air-support/tools/validate_native.py --case A01 --run-dir <original A01 bound run path> --read-only
python cases/simlox-air-support/tools/validate_native.py --case A02 --run-dir <original A02 bound run path> --read-only
```

Run both normal and replay paths named in `manifest.json`. That strict checker
intentionally requires the original Windows invocation/closure paths; do not
rewrite them for AMD128. To regenerate the checked self-authored input bytes,
use each case README's `generate_native.py --case ... --output <fresh path>`
command and compare the input SHA in the manifest. No native recalculation is
part of this handoff.

## Metric and state boundaries

Native times are hours; pairing times are minutes (`×60`). The sole native
aircraft instance is `<TEACH-AIR-01,0>`. Mission instance IDs include
`TEACH-UNIT` and ordinal `0` for A01, `0..2` for A02. A01 notices at 7 h,
allocates and loses ready then, reserves until launch at 8 h, completes at
10 h and returns ready. A02 repeats at notices 7/19/31, launches 8/20/32 and
returns 10/22/34 h. The aircraft is **not ready** between notice and launch.
`FTMO × interval_width` integrates to 2/6 mission-operation **hours**;
`NSYMO/NSYMA/NSYMR/NSYRY × interval_width` integrate to aircraft-hours:
A01 `2/3/1/33`, A02 `6/9/3/27`. The native inner task at 8.5–9.5 h
(and +12/+24 h) is retained as native-only until an engine mapping is agreed.
Native `SystemResults` rows are scoped to `Total over all Units` and
`Total over all Systems`; these totals equal the sole aircraft in A01/A02,
which does not establish a SID-specific report mapping for multiple aircraft.
Native zero-time preparation log markers are bookkeeping; NPSTA=0 means no
modeled preparation work. One wave equals one sortie here only because there
is exactly one aircraft per wave.

SIMPE=36 h for normal cases. Five early SIMPE inputs (7.5, 9, 9.9999, 10,
10.0001 h) failed conversion #204; positive 10.5/12 h inputs succeeded.
These sampled inputs do not define a cutoff formula or event priority.
RCEND-only probes keep the full 8–10 h ENLOG while SystemResults clips to
7.5/9/9.999899864/10/10.000100136 h (native float endpoints).
ResultSummary remains 0–36 h. At RCEND 9 h, native MSUF=1 although the
mission is still in flight and completes at 10 h; that fraction is not a
completed-by-window-end count. At 7.5 h, the mission is notified-pending,
not in flight. The manifest gives field-specific tolerances and provenance.

No resource, stock, PM, CM, fault, cancellation, tie-priority or cross-engine
capability is proven by these empty-mechanism cases. Identical integer RNG
seeds do not establish a shared random stream. The next engine gate is an
independent execution with explicit aircraft/mission identity mapping,
72-bin state comparison, terminal counts and first discrepancy. GUI review
still awaits private Windows App connection; the included checklist is a
request for evidence, not a record of completed screenshots.
Read-only engine code inspection suggests an existing pre-support path for
notice and readiness, but this is only a mapping candidate until an engine
run demonstrates matching observables; no engine task is initiated here.
