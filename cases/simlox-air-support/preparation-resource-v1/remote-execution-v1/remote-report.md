# 4700-3 native execution report

The final source-bound snapshot was executed on `4700-3` with SIMLOX 2017 CLI.
Its remote root is
`C:\Users\user\Documents\Codex\2026-09-27\simlox-preparation-resource-v1-6539ea720ef2`.
The source manifest SHA-256 is
`6539ea720ef2b9c301889517da3cfdd8ff1eecfbb71dff48c32f85dbfd1bbe7a`;
the archive SHA-256 is
`ca430b78ddb99936475419f92b455d971b2502311630b413732e6ffe7a057c66`.
All 72 source files matched before execution. The SIMLOX executable remained
`fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0`.

## Result

All 12 active candidates completed import, JSON roundtrip, calculation, report
export, artifact sealing and strict validation. Every run returned
`cli_behavior_verified`, an empty difference list and an equal non-empty-table
roundtrip. No SIMLOX process remained after evidence collection.

| Case | Variant | Run ID | Native result |
|---|---|---|---|
| B01 | fixed-30m | `formal-b01-6539ea` | verified |
| B02 | serial-10m-20m rev 1.0.1 | `formal-b02-v101-6539ea` | verified |
| B03 | explicit-cold-hot | `formal-b03-6539ea` | verified |
| C01 | capacity-2 | `formal-c01-cap2-v101-6539ea` | verified |
| C01 | capacity-1 | `formal-c01-cap1-v101-6539ea` | verified |
| C01 | capacity-0 | `formal-c01-cap0-v101-6539ea` | verified |
| C01 | wrong-specialty | `formal-c01-wrong-v101-6539ea` | verified |
| C02 | both-available | `formal-c02-both-v101-6539ea` | verified |
| C02 | equipment-zero | `formal-c02-equip0-v101-6539ea` | verified |
| C03 | staffing-2 | `formal-c03-staff2-v101-6539ea` | verified |
| C03 | staffing-1 | `formal-c03-staff1-v101-6539ea` | verified |
| C03 | staffing-0 | `formal-c03-staff0-v101-6539ea` | verified |

The C03 timeline observed two personnel enabling both aircraft to prepare in
parallel and launch at 08:00. One person serialized the preparation work and
delayed launch to 08:30. Zero personnel produced two failed requests and no
launch. C01 and C02 negative variants likewise remained valid native models
whose expected result is waiting or no launch, rather than conversion failure.

## Superseded inputs

The earlier `b26313f353ab` snapshot contains 10 rejected inputs: B02 rev 1.0.0
failed conversion with error `#200`, and the nine original C01/C02/C03 inputs
failed with error `#167`. Those inputs and logs remain immutable historical
counterexamples. They are distinct from the 12 active inputs in the final
snapshot and were not relabeled as successful runs.

The intermediate `f8b2face730d` snapshot contains sealed calibration probes
used to derive and review the resource validator. Those probes remain
`sealed_probe_behavior_unverified`; the final status comes only from the fresh
`6539ea720ef2` strict runs.

## Evidence and acceptance boundary

The 204 final run files were copied to
`data/local/issue18-native/6539ea720ef2/v1` and remain local raw evidence.
Per-run input and run-manifest hashes, remote/local path patterns, and the 10
superseded failures are recorded in `evidence-index.json`.

Each run manifest states:

- `acceptance_scope: isolated_contract_cli`
- `publication_state: not_published`
- `prerequisites_state: not_all_published`
- `gui_status: not_run`
- `cross_engine_status: not_run`

Therefore these results verify the isolated deterministic CLI contracts. They
do not publish the 108-case catalog, complete the parent/GUI gates, establish
Python/Rust equivalence, or constitute general SIMLOX conformance.
