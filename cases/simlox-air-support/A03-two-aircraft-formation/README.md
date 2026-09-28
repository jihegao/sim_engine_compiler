# A03: two aircraft in one mission wave

This candidate fixes `A02@1.0.0` as the parent. The builder verifies its exact
input SHA-256 before changing three native tables. It keeps the 08:00 wave,
removes A02's 20:00 and 32:00 waves, sets `SystemDeployment.QTYPS=2`, and sets
`MissionType.NOS=MNOS=2`. Both aircraft share one native System type and Unit;
their runtime instance identities must be distinct. No preparation or resource
rows are added.

Run `python build.py --check` to verify the checked native input. The
`parent-diff.json` records every changed row. The validator reads the original
SIMLOX log, report, and roundtrip export and checks one mission instance with
two allocations, one launch, two distinct aircraft on that launch, two aircraft
on completion, and four aircraft-hours of mission operation. It rejects a
one-aircraft launch even when aggregate mission success is one.

The parent A01/A02 GUI gates remain pending. The candidate is not published.
`run_native.ps1` requires an active interactive `Console` or RDP user session;
this interactive runner rejects SSH/session-0 execution,
an existing run directory or an active SIMLOX process. Each run needs a new ID
and the checked input hash. It stores raw outputs in a unique directory, runs
both the preserved probe validator and the new source-bound strict summary
validator, and still marks the result as an isolated CLI check. The strict
validator checks the result window and one planned/successful mission wave.
GUI review, parent gates and an independent replay are separate requirements
for a formal case conclusion. The three retained probes and their original
source-bound results are indexed in `evidence-index.json`; their validator is
preserved byte-for-byte in `validate.py`.
RDP process presence alone does not prove that SIMLOX import, calculation or
report export works there. Check the visible license state and keep a failed
first RDP run as evidence rather than promoting the earlier CLI probes.
For an SSH CLI run, use the separate `run_native_ssh.ps1` entry point and its
`ssh_cli_v1` provenance contract. It requires an authenticated session-0 SSH
process with an `sshd.exe` ancestor and stores the host, original Windows run
path, and ordered UTC command timestamps. The strict validator checks that mode independently of the
interactive runner. An SSH result does not turn a CLI result into GUI acceptance.

During a read-only RDP inspection on 2026-09-28, SIMLOX 2017.2 displayed the
candidate input from `probe-a03-20260928-03/model.sxi`: `QTYPS=2`,
`MissionType.NOS=MNOS=2`, and a single `BASIC-SCHEDULE` operation profile
starting at 08:00. No new GUI calculation, report export, or source-bound
screen capture was produced, so GUI acceptance remains pending. SIMLOX must
stay open in the present RDP session; a concurrent SSH CLI run is excluded by
the runner's process guard.
