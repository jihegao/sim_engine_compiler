# D12.var02 post-run static review — 2026-10-04

**GO for the bounded direct TOP49-to-BIG48P5 CLI observation.** This review was read-only; I did not invoke SIMLOX or modify authored source or raw output.

The accepted D12.var01 active-small linked input, closure and sign-off hashes match the contract. Both child hashes match the frozen contract and runner. Relative to that parent, each child changes descriptive text and appends one TOP49 row to MaterielPM, PMLocation, Tasks, TaskBreakDown and SubTaskResource. The new pair differs only in description and `TOP49.PMRID` null versus `BIG48P5`; inherited `BIG48P5.PMRID=CAL24` is unchanged. The 60-hour collection windows remain in both arms.

Closure SHA-256 `028759b8af9453a6551e790eb0615e2c4c1f3fa303c1fd6560c77beb810950ad` has no error. The source hashes before and after execution agree, including contract and runner. All 22 raw file sizes and SHA-256 hashes agree with the closure and evidence index. Eight import/export/calc/report steps exited zero with GUI preservation. The author verdict is GO 159/159, SHA-256 `1590590870f8e177d10bfeea0dd3b52d751fc8abc385ddc3e52fd1797084dc59`; the separate independent verdict is GO 3,392/3,392, SHA-256 `30b33199e9e3262f1b7e0a1f06a419cf922a0a6f62249183cc81da033cc8437e`.

Native event traces match before hour 49. On aircraft 1, BIG48P5 task 5 is performing from 48.5 when TOP49 starts at 49. In the linked arm task 5 and its subtask receive stop events at 49 and release the worker after half an hour; TOP49 work then proceeds. BIG48P5 task 6 on aircraft 0 starts and stops at that timestamp with zero elapsed work. In the unlinked arm, both BIG48P5 subtasks finish their hour of work. A waiting CAL24 task also stops at 49 in the linked arm, but the pair cannot isolate automatic transitive cancellation through the chain. The logs do not expose internal PM counter values.

Both reports have 120 System, Resource and Stock half-hour rows. Direct sums of the raw reports give `NPMS/NPMT` 8/6 unlinked versus 8/4 linked, PM aircraft-hours approximately 6.5 versus 5.0, and worker-hours approximately 11.5 versus 10.0, including the same five repair hours. These figures agree with the sign-off and event worker leases. README and sign-off correctly distinguish direct middle-task interruption from unproven transitivity and general priority behavior.

**Limits:** One seed, two aircraft, one base, one worker and this specific due-time spacing. No general PMRID rule, automatic transitivity, counter-reset observation, ENFNC, remote-base, GUI or cross-engine result follows from this case.
