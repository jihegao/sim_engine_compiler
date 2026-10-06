# B04.var02 sufficient turnround crew v0.1.1

This bounded child adds one available `P-CREW` and a one-person demand on the first `TURN-STEPS` subtask of the accepted [B04.var05 parent](../B04-var05-turnround-breakdown-v0.1.0/README.md). All 221 parent authored cells remain; four resource/report rows add 28 cells. The frozen [contract](contract.json) and [parent-diff checker](check_parent_diff.py) define the exact input change.

The one approved SSH session-0 run is sealed locally at `runs/b04-var02-turn-resource-v011-ssh-20261006-01`. Run `python build.py`, `python check_parent_diff.py`, `python validate_native_cli.py runs/b04-var02-turn-resource-v011-ssh-20261006-01`, and `python review/independent_replay.py` to check source and read-only native evidence. `run_native_ssh.ps1` is bound to the original unique run ID and refuses an existing directory; do not rerun accepted evidence. Raw runs are ignored in Git and indexed by SHA-256.

The independent replay and [signoff](cli-scope-signoff-2026-10-07.md) support one sufficient resource arm only. The v0.1.0 prelaunch NO_GO and its original bytes remain in the adjacent excluded package, with an identical memo copy [here](review/excluded-v010-prelaunch-no-go-2026-10-07.md). Shortage, zero capacity and competition remain open.
