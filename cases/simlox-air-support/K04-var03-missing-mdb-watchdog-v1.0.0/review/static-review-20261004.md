# K04.var03 missing-MDB watchdog: independent static review

**Decision: GO as a sealed, time-bounded diagnostic; NO-GO as a reusable native missing-file outcome.** The child had no native terminal result. This review did not invoke SIMLOX, mutate the registry, or edit authored or raw files.

## Frozen setup and provenance

- The contract SHA-256 `815fcd34e9ef2d8c2f643ae5118786a2f584ad36b4d8757fe2e6163d62d51ebf` is literal in the runner; PowerShell parsing has zero errors. The accepted K04.var02 SXI, closure, sign-off, main input, event log, report, executable and manual match the runner's pins. The runner SHA-256 is `a5abb8f0232f0c2703449ef06c80fed247b6345473a33892d09f3a88d9a6b21d`.
- The isolated `model.sxi` is byte-identical to accepted K04.var02 (SHA-256 `7d0920e7b099d2f0eabb1dc2c69279de303cfec19c548405907aa07beab4e78a`) and retains `INCFN=level1.mdb`. Its run directory has no `level1.mdb`; the requested process working directory is the accepted parent's run directory, which has the pinned MDB. Thus the case tests a missing file beside the relocated SXI despite a file with the same name in the requested working directory.
- Closure SHA-256 `315d8707481e5c482f138704e3d07a9bb62dd17820776ce1d0ff6c0b4bd8f42e` seals five raw files; I independently recomputed every SHA-256 and size, with no mismatch or unlisted raw file. Invocation hash and all source hashes before/after also match.

## Observation and safety

- The log stops after `Including data from file:` followed by the missing **isolated SXI directory** path. It contains no converter completion marker, error code, successful output, or simulation result. `model.sxo` is four bytes; `model.log` is absent. A generated `$5460@model.sxi$` file is included in the raw seal.
- At the 20-second and 45-second watchdog snapshots, PID 5460 was still a session-0 `Simlox.exe` child with a command line containing this exact SXI, a zero main-window handle, and unchanged 0.515625 seconds of CPU time. The runner rechecked name, session, and command line before stopping that PID only. The observation records `watchdog_terminated_after_45_seconds`, exit code `-1`, no wrapper error, and the child absent in the final snapshot. This is a **watchdog-terminated stall observed through 45 seconds**, not a native rejection, a proof of indefinite hang, or a GUI-dialog finding.
- The runner required session-0 SSH and an `sshd.exe` ancestor, held `Global\SimloxIssue18NativeQueue`, verified the active protected GUI's PID/session/start, and restored the original MDB association in cleanup. The invocation and observation record GUI PID 13340/session 1 and original association `mdb=Microsoft Access Driver (*.mdb)|` after the stop. A current read-only check found that same GUI PID/session/start and association, with no remaining PID 5460. This supports protected-GUI preservation in the recorded run; historical state still depends on the runner's sealed checks.

## Claim boundary

The accepted K04.var02 parent showed successful relative top-level MDB resolution when the MDB existed beside its SXI. This new diagnostic shows that the relocated, identical SXI attempted the missing path beside itself and had not finished conversion after 45 seconds, even though the requested process working directory contained `level1.mdb`. It does not establish the application's complete search order, the reason for the stall, a general missing-MDB error behavior, an interactive dialog, or a reusable calculation result. The contract's `diagnostic_pending_native` state is frozen pre-run metadata; publication prose should classify the actual outcome as a **sealed watchdog diagnostic** and retain the explicit NO-GO for a native terminal missing-file claim.
