# I05.var06 CLI scope signoff — 2026-10-05

**Candidate scope:** one scheduled `ChangesMissionPreparation.DURN` update at h10, from four hours to one, on the existing B01 `BASIC-MISSION`/`TEACH-AIR-01`/`BASE-01` preparation record. This accepts one bounded I05.var06 slice; the other `Changes` tables and full I05 remain unverified.

The guarded session-0 SSH run `i05-var06-prep-change-v100-ssh-20261005-01` completed 8/8 import, export, calculate and report steps. Each arm had converter errors zero, reviewed warnings 108 and 126, and notes zero. All 16 row-containing authored tables per arm, including the control's all-null placeholder, match native export by columns, datatypes and rows. The closure seals 22 local raw files and unchanged source hashes, with protected GUI identity preserved around every native child.

Native events show the first preparation start h9, planned four-hour subtask, and finish h13 in both arms despite the source-frozen h10 DURN1 change. The later task starts h20 and finishes h24 in control versus h21 with the change. The corresponding `SystemResults` bins total eight versus five preparation aircraft-hours; 72 consecutive half-hour system and stock bins, zero failures/damage, two successful h13–15 and h24–26 missions, and terminal one ready aircraft reconcile with events. Author replay passes 105/105 checks. Publication requires a separate independent replay to pass. Native log does not separately announce the h10 change event; the change time and new value are frozen in the input and their effect is directly observed on the later task.

The report's one trailing comma is normalized in memory only for parsing. Raw bytes stay in ignored local `runs/` and their hashes are published in `evidence-index.json`.

**Limits:** one seed, one existing preparation record, DURN only and two separated notices. No DURND, subtasks, queued task, same-time tie, other `Changes` tables, GUI, cross-engine, or full Issue #18 claim.
