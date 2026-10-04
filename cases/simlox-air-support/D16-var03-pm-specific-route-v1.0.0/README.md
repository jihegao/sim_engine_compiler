# D16.var03 v1.0.0 excluded diagnostic

This frozen pair tested an explicit `PMStationStructure` route for the remote CAL24 task against the ordinary `StationStructure` link. Its [guarded run](run_native_ssh.ps1) completed eight steps and showed 0.25-hour default versus 1-hour PM-specific travel in both directions for both aircraft. The [independent replay](review/independent-verdict.json) passed 615/618 checks but returned **NO_GO_FULL_CONTRACT**: native export added optional `CFRMS` and `CTOMS` columns to the route table in both arms and an all-null placeholder row to the default arm. Those three exact-roundtrip failures exclude this version from the publication index.

The [evidence index](evidence-index.json) retains 22 local raw seals and the [v1.0.1 candidate](../D16-var03-pm-specific-route-v1.0.1/contract.json) pins this diagnostic closure. The revised candidate freezes the native 13-column shape and explicit default placeholder before another run.
