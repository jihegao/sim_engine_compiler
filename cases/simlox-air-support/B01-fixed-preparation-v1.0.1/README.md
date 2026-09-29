# B01 1.0.1: fixed preparation on the A01 normal path

The [2026-09-29 source-bound review](evidence-2026-09-29.md) accepts and
publishes this bounded B01 1.0.1 model after a fresh native run and independent
replay with corrected invocation closure and global preparation-event checks.
B01 1.0.0 remains unpublished.

The [permanent loopback SSH verification](loopback-ssh-verification-2026-09-29.md)
records a later, source-bound B01 rerun using the user's verified local key.

This version derives from the SHA-256-pinned A01 native input. It keeps A01's
`TEACH-AIR-01`, `TEACH-UNIT`, `BASIC-MISSION`, `BASIC-SCHEDULE`, one-hour notice,
two-hour mission, 36-hour horizon, half-hour result interval and seed. The
complete normalized parent diff adds exactly one `MissionPreparation` row and
one `Tasks` row. No existing row or field changes. The frozen B01 1.0.0 source
and run remain separate and unchanged.

The [observable contract](contract.json) expects one fixed 30-minute
preparation for the assigned aircraft, starting at 07:00 and completing at
07:30. The scheduled mission remains at 08:00–10:00. This configuration checks
positive preparation work and ordering; it does not show that preparation
delays a launch because work ends before the planned start. An internal
preparation-object creation count is not observable and is excluded.

Use `python build.py --check` to verify the checked [native input](native-input.json)
and [exact parent diff](parent-diff.json). The `run_native_ssh.ps1` script
requires an authenticated session-0 SSH process with `sshd.exe` ancestry,
the existing responsive SIMLOX GUI PID 13340 in its logged-on session,
`-AllowExistingGui`, a new run ID and
the contract's input SHA-256. It obtains the host-wide native queue mutex,
launches each CLI step hidden, and checks that the GUI survives each step. It
never stops, closes, restarts or interacts with that GUI. Failed runs retain
their unique directories and must not be overwritten.

From the authenticated SSH PowerShell session on 4700-3, with this checkout
available at `$repo`, run:

```powershell
powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$repo\cases\simlox-air-support\B01-fixed-preparation-v1.0.1\run_native_ssh.ps1" -RunId "b01-v101-ssh-20260929-01" -InputSha256 "2c5485a20bbad5404a706a9a55fad6b46d78679e7c087f7bb33da3af35b1a78b" -AllowExistingGui
```

The runner records import, native JSON roundtrip, calculation, report export,
raw closure hashes and behavior validation. Independent read-only review checks
the raw source, events, report, provenance, parent behavior and declared limits.
GUI sampling is optional under the 2026-09-29 Issue #18 standard; CLI output
cannot prove GUI-only functions. B02 requires a separate model and acceptance.
