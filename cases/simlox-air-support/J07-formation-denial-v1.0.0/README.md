# J07 fixed-demand formation metrics, v1.0.0

This package covers the bounded CLI scopes `J07.var01` (single-aircraft control) and `J07.var02` (one two-aircraft formation compared with a later, unfilled three-aircraft demand). The [sign-off](cli-scope-signoff-2026-10-01.md) states the observed behavior and limits. It does not complete J07.

## Inputs and lineage

`single-control-input.json` and `formation-control-input.json` are byte-identical copies of the accepted A01 and A03 inputs. `denied-demand-input.json` extends A03 with one mission type requiring three aircraft and one scheduled demand at hour 12. The deployment remains two aircraft. [contract.json](contract.json) freezes the pre-run hypothesis and source fingerprints; [exact-diff.json](exact-diff.json) lists every changed table. `build.py` regenerates the three inputs from the accepted parents and checks their hashes.

The schedule orders each demand an hour before the requested launch. In the denied-demand run the first two-aircraft mission starts at 8 and succeeds at 10. The second is ordered at 11, receives both available aircraft, cannot obtain a third, and is cancelled at 12.3333 before launch. Its temporary allocation counts as assigned time in `SystemResults`, not as another sortie or accomplished mission time.

## Reproduce and inspect

Run `python build.py` to check the frozen inputs. On this Windows host, `run_native_ssh.ps1` requires authenticated session-0 SSH, the installed SIMLOX executable, and the original GUI PID 13340. It serializes native work with `Global\SimloxIssue18NativeQueue`. Run `single-control`, `formation-control`, and `denied-demand` sequentially with fresh run IDs. The runner captures five steps: import, export, calculation, JSON report, and exact source-roundtrip check. Every raw run has an immutable `closure.json` listing byte counts and SHA-256 hashes; `runs/` is intentionally ignored by Git and retained locally.

`python validate.py` replays the author assertions against the three named local runs and writes `review/author-validation-2026-10-01.json`. The separate `review/independent_readonly.py` reads the frozen inputs and raw files without importing the author code. The JSON export parser normalizes SIMLOX trailing commas in memory only; raw bytes remain sealed. Published Git files contain the model inputs, executable validation code, review results, and evidence hashes, not bulky or proprietary native data.

## Interpretation

For the first successful wave, one mission and two aircraft sorties are separate counts. The denied child has two planned fixed missions but only one start and success. It therefore reports `MSTF=MSUF=1/2`, `MTMF=2/4`, and `STMF=4/(4+6)`. The two allocated aircraft during the later cancelled demand add assigned exposure but no operation exposure. The source input supplies the planned denominators; the native event log and `SystemResults` supply observed starts, success, aircraft time, and return readiness.

Partial success, a success point before mission completion, unit/group/type output aggregation, regenerative denominator behavior, GUI rendering, and cross-engine behavior remain unverified.
