# I05.var06 — change preparation duration while a task is running

This bounded pair derives from accepted B01 fixed preparation. Both arms have one aircraft, an existing `MissionPreparation` record with DURN4, a four-hour notice, and missions scheduled at h13 and h24. The control has an all-null `ChangesMissionPreparation` placeholder. The change arm sets that record's DURN to one hour at h10.

The first preparation starts at h9 and runs for four hours to h13 in both arms. The h10 change does not shorten it. The later preparation starts at h20; it runs four hours to h24 in control and one hour to h21 with the change. Both missions launch at h13 and h24 and complete successfully at h15 and h26. `SystemResults` half-hour bins show eight versus five total preparation aircraft-hours. This experiment demonstrates task-start parameter retention and subsequent use of a scheduled duration change, without a launch-time difference.

`build.py` recreates byte-pinned inputs, `run_native_ssh.ps1` guarded eight native CLI steps, and `validate.py` plus a separate read-only reviewer replay check source pins, roundtrips, native events and report bins. The raw SXI/SXO/log/report evidence remains in ignored local `runs/` and is sealed by `evidence-index.json`. Each native report JSON has one trailing comma; checkers remove that comma only in memory to parse it and preserve raw bytes.

This covers one deterministic DURN change on one existing preparation record at one seed. DURND, subtasks, queued tasks, same-time ties, other `Changes` tables, GUI and cross-engine parity remain untested.
