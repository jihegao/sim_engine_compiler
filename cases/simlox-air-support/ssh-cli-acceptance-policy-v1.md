# Issue #18: SSH CLI execution policy (2026-09-28)

The owner confirmed on 2026-09-28 that SIMLOX CLI runs over SSH may be used for
the CLI portion of native model acceptance. A successful SSH run of the
`aircraftorg` Demo produced a conversion log and nonempty SXO; that smoke test
does not accept any case in this library. This decision supersedes the earlier
Console-only restriction for **CLI execution only** in
`4700-3-local-console-acceptance-handoff.md`.

GUI calibration and GUI acceptance require a visible, verified active Console
or RDP user session. RDP use must be checked in the actual SIMLOX windows and
recorded as GUI evidence; merely seeing a process is insufficient. SSH results
must keep `gui_status=not_run` and cannot promote a case to
`native_behavior_accepted` or `reusable_published` without its other gates.
The old Console runner and historical run evidence remain unchanged.

The [2026-09-24/25 efficiency record](../../docs/simlox-feasibility-benchmark.md)
used hidden PowerShell-launched SIMLOX processes for four official Demo models.
On 2026-09-25, 12 reruns succeeded while a SIMLOX process from the previous
day was present. The record does not establish whether the GUI was open when
the 2026-09-24 first run began. Thus an existing GUI is not, by itself, a
proven SIMLOX CLI limitation; the A03 runner's default stop is a safety policy.

On 2026-09-28 at 23:19 local time, a separate RDP desktop CLI smoke test of
the bundled `aircraftorg.sxi` Demo exited with code 0 but produced no requested
JSON. The SIMLOX license log reported `Terminal client access is not allowed!`.
This is a failed RDP CLI route, not a successful simulation. The original
probe input remained in
`C:\Users\user\AppData\Local\Temp\codex-simlox-local-cli-probe-312fb3f1669149bbba4476eb8b22de73`;
the expected `aircraftorg.json` was absent. The evidence is the 4700-3 Codex
session transcript at
`C:\Users\user\.codex\sessions\2026\09\28\rollout-2026-09-28T22-25-12-01a0e224-34c6-7961-bf32-95fb53c11aa2_01a0e867-d030-7b32-995e-cbe370cca50d.jsonl`
(lines 715, 718 and 725) and `OpusSuite_key.log` line 26; do not copy the full
license log into the repository. This denial applies to that RDP-launched
probe; it does not establish that a session-0 SSH launch is denied.

At 23:40 local time, a separate SSH session-0 smoke test exported a copy of
the bundled `aircraftorg.sxi` while the RDP GUI process (PID 13340, session 1)
remained open. The hidden child (PID 7948) exited 0, produced a 39,360-byte
JSON with a `model` root and an export-completed log, and the original GUI PID
was still present afterward. The raw input, output, log and receipt are in
`C:\Users\user\Documents\Codex\2026-09-28\simlox-ssh-gui-coexist\demo-20260928-234007`.
This proves only the bounded Demo export under GUI coexistence, not A03
calculation, source semantics or GUI acceptance. Keep the current GUI running
as requested by the owner.

For each new SSH CLI run:

1. Use a new run ID and directory; record host, original Windows run path, SSH
   session markers and `sshd.exe` process ancestry, SIMLOX executable hash,
   runner hash, frozen input hash,
   exit codes, and per-step UTC timestamps.
2. Allow only one CLI job at a time. By default, an existing SIMLOX process is
   a stop condition. `-AllowExistingGui` permits exactly one pre-existing
   process in an active interactive session; record its PID, session and start
   time, reject any other process, and verify it survives every command. Do not
   close the user's GUI window.
3. Check import, nonempty roundtrip export, zero conversion errors, nonempty
   SXO and event log, report export, source-bound behavior assertions, and
   closure hashes. Exit code zero alone is insufficient.
4. Preserve raw outputs and failed attempts. Independent review must replay
   assertions on read-only copies before any CLI-scope acceptance conclusion.
5. Keep parent, GUI, publication, cross-engine, and unsupported-capability
   statuses explicit. An isolated CLI pass is not a published case.

`A03-two-aircraft-formation/run_native_ssh.ps1` is a new runner for this policy.
Its `ssh_cli_v1` provenance is checked separately by the source-bound strict
validator. The existing `run_native.ps1` retains its interactive behavior and historical
identity. Resource cases need their own versioned SSH runner before formal
reruns; their frozen v1 runner and evidence must not be rewritten.

On Windows, use `preparation-resource-v1/check_generated_portable.py` for the
read-only static source check. It normalizes manifest path separators for
comparison while leaving all frozen v1 files unchanged.
