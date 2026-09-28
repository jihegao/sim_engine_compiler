# Issue #18: SSH CLI execution policy (2026-09-28)

The owner confirmed on 2026-09-28 that SIMLOX CLI runs over SSH may be used for
the CLI portion of native model acceptance. A successful SSH run of the
`aircraftorg` Demo produced a conversion log and nonempty SXO; that smoke test
does not accept any case in this library. This decision supersedes the earlier
Console-only restriction for **CLI execution only** in
`4700-3-local-console-acceptance-handoff.md`.

GUI calibration and GUI acceptance still require a visible local Console
session. SSH results must keep `gui_status=not_run` and cannot promote a case to
`native_behavior_accepted` or `reusable_published` without its other gates.
The old Console runner and historical run evidence remain unchanged.

For each new SSH CLI run:

1. Use a new run ID and directory; record host, SSH session markers, SIMLOX
   executable hash, runner hash, frozen input hash, exit codes, and timestamps.
2. Allow only one SIMLOX job at a time. An existing SIMLOX process is a stop
   condition; do not close the user's GUI window.
3. Check import, nonempty roundtrip export, zero conversion errors, nonempty
   SXO and event log, report export, source-bound behavior assertions, and
   closure hashes. Exit code zero alone is insufficient.
4. Preserve raw outputs and failed attempts. Independent review must replay
   assertions on read-only copies before any CLI-scope acceptance conclusion.
5. Keep parent, GUI, publication, cross-engine, and unsupported-capability
   statuses explicit. An isolated CLI pass is not a published case.

`A03-two-aircraft-formation/run_native_ssh.ps1` is a new runner for this policy.
The existing `run_native.ps1` retains its Console-only behavior and historical
identity. Resource cases need their own versioned SSH runner before formal
reruns; their frozen v1 runner and evidence must not be rewritten.

On Windows, use `preparation-resource-v1/check_generated_portable.py` for the
read-only static source check. It normalizes manifest path separators for
comparison while leaving all frozen v1 files unchanged.
