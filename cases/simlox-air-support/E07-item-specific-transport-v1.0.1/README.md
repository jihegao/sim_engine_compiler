# E07 item-specific transport on an accepted E04 route

This case derives from the accepted E04 FAST upstream-stock input. Its general `StationStructure` remains BASE-01→DEPOT-01 with two hours of transport in either direction. One complete `ItemStationStructure` row for `TEACH-LRU-01` sets one hour down and three hours up. Stock, repair location, missions, seed and other business rows remain fixed.

Run `build.py` to verify the frozen source and `describe_diff.py` to verify its exact two-table delta. `run_native_ssh.ps1` requires guarded session-0 SSH and the host-wide mutex; it generated the original ignored run `e07-item-route-v101-20261001-01`. `validate_native.py` and the independent `review/independent_readonly.py` replay original raw events and reports. [Evidence index](evidence-index.json) records raw file lengths and hashes; [signoff](cli-scope-signoff-2026-10-01.md) defines the bounded accepted behavior.

The [v1.0.0 candidate](../E07-item-specific-transport-v1.0.0/README.md) is retained only as an excluded schema diagnostic. Its native export inserted two nullable columns absent from the authored input, so exact roundtrip failed. v1.0.1 includes those columns and has a fresh native run.
