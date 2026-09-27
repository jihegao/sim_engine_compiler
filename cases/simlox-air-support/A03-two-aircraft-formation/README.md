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
`run_native.ps1` supports an isolated CLI capability probe now; a formal case
run remains gated on parent and A03 GUI calibration. Each run needs a new ID.
The runner requires the checked input hash, refuses an existing run directory
or active SIMLOX process, and stores raw outputs in a unique directory. The
three retained probes and their source-bound result are indexed in
`evidence-index.json`.
