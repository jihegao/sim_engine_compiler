# Resource allocation point repair v1

Status: generated C01--C03 revision 1.0.1; native behavior pending sealed
4700-3 probes.

## Diagnosis

All nine C01--C03 revision 1.0.0 inputs reached SIMLOX import and roundtrip,
but native conversion stopped in `MissionPreparation` with error `#167`:
`All required resources are not available at station (STID): BASE-01`.
Each resulting SXO was four bytes, so none supplies resource or mission behavior
evidence.

The installed SIMLOX 2017 table dictionary identifies `Control.APID` as the
allocation point identifier and lists `ResourceAllocation.POINT` among its
related fields. The source is `SIMLOX-2017-TABLE-DICTIONARY`,
`Control` column 4 and `ResourceAllocation` column 1, SHA-256
`11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0`.
The retained working J35 resource probe corroborates this relationship:
`Control.APID=J35` and all twelve `ResourceAllocation.POINT` values are `J35`.

The failed teaching inputs instead used `Control.APID=AIR_BASIC` and
`ResourceAllocation.POINT=AIR-TYPE`. This cross-field mismatch explains why
SIMLOX could not see even positive resource capacities at `BASE-01`.

## Repair and preservation

Revision 1.0.1 changes only C01--C03 resource allocation points to
`AIR_BASIC`, matching `Control.APID`. The generator now rejects a resource
allocation whose `POINT` is absent from the selected Control allocation point.
The C03 staffing siblings still differ by exactly one field:
`ResourceAllocation.RQTY` for `P-CREW`.

The nine revision 1.0.0 JSON inputs remain byte-for-byte unchanged. Their
paths, hashes, `#167` diagnostic, and rejected status are recorded in
`native/manifest.json` and the three contracts. They are not selectable for
acceptance.

The repair does not change C03's 07:30 preparation notice, 08:00 planned
launch, two required aircraft, 30-minute work per aircraft, or staffing
capacities 2/1/0.

## Verification boundary

Local generation and contract checks prove schema, row relationships,
revision selection, immutable failed snapshots, and the intended normalized
delta. They do not prove native request, wait, acquire, release, preparation,
formation launch, or cancellation behavior. The first native gate is a sealed
positive probe for C03 staffing 2 and staffing 1. Zero-capacity or
wrong-specialty conversion rejection, if observed after this repair, is an
explicit native input boundary and must not be relabeled as a simulated wait.
