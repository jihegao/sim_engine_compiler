# J06 percentile probe v1.0.0 — excluded

This input appended `PercentileLevels(0.75)`, `SnapshotResultTimes(9,11)`, and a System `TOTAL=TIME=SNAPS=Y` replication-control row to accepted J04.var01. The guarded session-0 SSH run `j06-system-replication-v100-ssh-20261004-01` completed import, export, and calculation with zero converter errors but emitted runtime **warning #502: “All percentiles on SYDT could not be calculated.”** The frozen #108/#126/#211-only gate stopped before report export. [Local closure](runs/j06-system-replication-v100-ssh-20261004-01/closure.json) SHA-256 `994f700c6917ed3b887d0c88259381f1c4727c4e10e563a7c3d060badebd04c8` seals the partial run and its error. GUI PID 13340 was preserved.

No percentile behavior is accepted or published from this probe. The narrower v1.0.1 package omits `PercentileLevels` and tests System replication TOTAL/TIME/SNAPS only. The v1.0.0 package is source and negative-evidence provenance, not a publication-index entry.
