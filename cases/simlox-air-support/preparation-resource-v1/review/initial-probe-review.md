# Initial native probe review

Reviewed at `2026-09-27T21:43:23+08:00`. This is an independent, local,
read-only review of the copied `4700-3` artifacts under
`data/local/issue18-native/b26313f353ab/v1`. The review did not start SIMLOX,
change implementation files, or claim GUI or cross-engine acceptance.

## Findings

- B01 and B03 have complete invocation-to-closure hash chains. Every artifact
  byte count and SHA-256 in each closure matches the retained file, and each
  probe manifest matches its invocation and closure. Both probe manifests say
  `sealed_probe_behavior_unverified` and `validator_executed=false`.
- B01 directly records preparation from 07:30 to 08:00, launch at 08:00 and
  mission completion at 09:00 for `<AIR-TYPE,0>` and `MISSION-BASIC`.
- B03 directly records a `COLD-FIRST` preparation from 07:30 to 08:00 with
  10-minute and 20-minute steps. It records `HOT-SORTIE` preparations from
  11:50 to 12:00 and 15:50 to 16:00 with one 10-minute step each. All three
  missions use the same native aircraft. This supports the user-approved
  explicit cold-task/hot-task modeling method.
- The B03 probe is bound to contract SHA-256 `dc409009...`. The later working
  tree contains a different B03 contract snapshot, so this probe remains
  calibration evidence and cannot be promoted to verification of that later
  snapshot.
- All three C03 variants complete import, export and row roundtrip, then SIMLOX
  rejects calculation with MissionPreparation error `#167`. Each SXO is four
  bytes. None has `model.log`, raw report, closure, probe manifest or run
  manifest. C03 therefore has no resource request/wait/acquire/release or
  formation-launch behavior evidence and remains native-unverified.

## Acceptance boundary

Closure proves retained-file identity. It does not prove behavior. Resource
acceptance requires the timestamped lifecycle for each aircraft and resource;
aggregate totals are insufficient. C03 remains the approved two-aircraft,
same-formation case. A future final native review must be added separately and
must not overwrite this record.

The machine-readable record is
[initial-probe-review.json](initial-probe-review.json).
