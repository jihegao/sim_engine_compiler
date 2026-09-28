# A03 source-bound SSH CLI run with an existing GUI

Run `a03-ssh-gui-20260928-02` was made on 4700-3 on 2026-09-28 from the
isolated checkout at commit `ffaa657a2c677f278843477f2298315bdd077dee`.
The frozen input SHA-256 is
`51e3f99ecf86e05e35dce2b2c9e062b483a2c0f3dd64625761bc64c45900cce6`.
The original run directory is
`C:\Users\user\Documents\Codex\2026-09-28\simlox-issue18-ssh-current\cases\simlox-air-support\A03-two-aircraft-formation\runs\a03-ssh-gui-20260928-02`.
The 16 original run files also have a byte-verified local copy in the ignored
`data/local/simlox-a03-ssh/a03-ssh-gui-20260928-02/` directory. Its ZIP archive
is `data/local/simlox-a03-ssh/a03-ssh-gui-20260928-02.zip`, SHA-256
`0bb05b815ac46d969301f2f4725cbb0a5d78b3aa7ae7c0bc209f878e65c0d46f`.
Neither raw location is committed. The run's `closure.json` SHA-256 is
`7895267c4cb4781049f96eb9948d8d939d01d26cab9fa79d1d2e29e385db5e02`;
`run-manifest.json` SHA-256 is
`7c5d9afbeb0f6a3333f41a6f172ed2aa3d711760959d202df281817c62cad2bc`.

The invocation records `ssh_cli_v1`, SSH ancestry, session 0, and the
`Global\SimloxIssue18NativeQueue` mutex. It admits the existing RDP GUI only
through `-AllowExistingGui`. That process was PID 13340 in session 1, started
at `2026-09-28T10:09:56.8261381Z`; the runner verified the same identity
before and after each native command. A later independent SSH readback found
that GUI process still running. The four ordered steps—JSON import, native
roundtrip export, calculation, and JSON report export—each exited 0 and took
about one second of process wall time. These are process timings, not SIMLOX
pure simulation timings.

An independent read-only reviewer copied the raw run, checked the 11 raw file
size/hash entries in `closure.json`, confirmed source hashes against the
checkout, checked the manifest and reran both validators. Both returned
`passed: true` and no differences. The native roundtrip retained all 10
nonempty business tables. The event log records a 07:00 allocation of two
distinct aircraft to one mission, one 08:00 wave launching both, and 10:00
completion of both. The input plans one wave, and ENLOG confirms its launch
and success; the report's `MSTF=MSUF=1` are aggregate ratios, not mission
counts. It also records `NREP=1`, `RTILW=0`, and `RTIUP=36`. Its 72 half-hour
intervals cover 0–36 hours; the four intervals in [08:00, 10:00) report
`NSYMO=2` and `FTMO=1`. `run.log` has zero
errors. Its only warnings are #108 (ENLOG enabled) and #126 (the teaching
System has no Item child); the validator checks this exact allowlist.

**Acceptance scope:** `isolated_contract_cli`; publication `not_published`.
This run proves a bounded SSH CLI calculation while the existing GUI process
remained open. A GUI process check and a read-only GUI table inspection do not
prove GUI calculation or report export. A01/A02 parent GUI gates, A03 GUI
source-bound acceptance, and publication remain pending. The A03
`ProblemDescription` text still describes the one-aircraft parent; correct it
in a new version and rerun its acceptance rather than rewriting this record.
