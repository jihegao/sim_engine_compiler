# Issue #18 final native run review

Review date: 2026-09-27 (Asia/Shanghai)
Snapshot: `6539ea720ef2`

## Conclusion

All 12 frozen B01--C03 runs passed an independent read-only replay of their
fixed contracts. The accepted result is limited to `isolated_contract_cli`.
Every run remains `not_published` with `not_all_published` prerequisites. GUI
and cross-engine checks were not run.

## Independent evidence checks

- Recomputed all 144 closure-bound raw artifact sizes and SHA-256 hashes: no
  mismatch.
- Recomputed all 12 invocation source-hash maps against the current frozen
  candidate input, runner, binding, validators, generator, contract, parameters,
  manifest, schema, writer, README, and A01 parent parameters: no mismatch.
- Verified all invocation, closure, validation, normalized-report, and run-manifest
  hash chains: no mismatch.
- Replayed conversion checks, JSON round trips, input mappings, event behavior,
  and report behavior from the sealed local copies: 12/12 passed.
- Confirmed all native command steps have the planned order and arguments, the
  shared invocation identity, and exit code zero.
- Confirmed the snapshot contains 204 files: 17 files for each of 12 runs.
- Cross-checked all 12 evidence-index tuples against the local input and
  run-manifest hashes and boundary fields: no mismatch.

The replayed C03 report assertion uses Python tuples in memory while JSON stores
the same values as arrays. This representation difference was normalized before
comparison; the values and pass result are identical.

## Run results

| Case | Variant | Behavior result | Assertions | Scope |
|---|---|---|---:|---|
| B01 | fixed-30m | passed | event timeline and interval report | isolated contract CLI |
| B02 | serial-10m-20m | passed | serial task timeline and interval report | isolated contract CLI |
| B03 | explicit-cold-hot | passed | cold/hot task timelines and interval report | isolated contract CLI |
| C01 | capacity-2 | passed | 6/6 | isolated contract CLI |
| C01 | capacity-1 | passed | 7/7 | isolated contract CLI |
| C01 | capacity-0 | passed | 7/7 | isolated contract CLI |
| C01 | wrong-specialty | passed | 7/7 | isolated contract CLI |
| C02 | both-available | passed | 8/8 | isolated contract CLI |
| C02 | equipment-zero | passed | 9/9 | isolated contract CLI |
| C03 | staffing-2 | passed | 8/8 | isolated contract CLI |
| C03 | staffing-1 | passed | 8/8 | isolated contract CLI |
| C03 | staffing-0 | passed | 7/7 | isolated contract CLI |

Full invocation, closure, validation, and run-manifest hashes for each run are in
`final-run-review.json`.

## Acceptance boundary

This review proves the fixed B01--C03 contracts against the SIMLOX CLI artifacts
in this snapshot. It does not publish the cases, promote the catalogue, close
unmet parent-case dependencies, verify GUI behavior, or establish cross-engine
equivalence. C03 staffing-0 records the observed cancellation at minute 510 for
this fixed profile; the general cancellation rule remains part of unverified C04.

The earlier `initial-probe-review.md` is an immutable review of the historical
`b26313f353ab` snapshot. Its conversion failures and old contract bindings do not
describe this final snapshot. The failed historical inputs and raw evidence remain
retained.
