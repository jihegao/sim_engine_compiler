# Preparation and shared-resource contracts v1

The [B01 1.0.1 case](../B01-fixed-preparation-v1.0.1/README.md) is a separate
versioned A01-derived model with a two-row parent delta and its own new SSH
native evidence. Its dated review publishes only that fixed profile. This v1
bundle and the original B01 1.0.0 evidence remain frozen.

The [2026-09-29 B01 `fixed-30m` CLI review](review/B01-fixed-30m-cli-review-2026-09-29.md)
accepts the observed positive-duration execution only in CLI scope under the
revised Issue #18 standard. B01 remains `not_published`: its original
contract changes the parent's business IDs and asks for a preparation-create
event the native log does not expose. The frozen 2026-09-27 run status remains
historical; B02–C03 keep their separately recorded gates. The B01 parent
diff has 11 changed tables, so its one-sentence declared delta is incomplete.

This package defines the business and native-acceptance contracts for the first
preparation/resource chain: B01, B02, B03, C01, C02 and C03. The contracts are
frozen expectations for deterministic teaching cases. They are not records of
SIMLOX execution.

The contract parent tree is:

```text
A01 -> B01 -> B02 -> B03
                 -> C01 -> C02 -> C03
```

This tree shows which case supplies each contract's model delta; it is not the
complete acceptance-prerequisite graph. The additional instructional gates are:

```text
A01 -> A02 -> A03 -> C03
       |             ^
       +----> B03    |
B02 --------> B03    |
C02 ----------------+
```

Thus B03 requires both B02 and A02. C03 requires both C02 and A03. A03 is not
implemented in this package, so a bounded native C03 resource probe does not by
itself establish that all catalog prerequisites are complete.

B03 uses the user-approved `explicit-mission-type-v1` business contract.
`COLD-FIRST` represents the first-wave cold-start sortie and `HOT-SORTIE`
represents later hot sorties. The mission type selects the preparation recipe.
This business contract is accepted. Its frozen CLI run passed an isolated
contract check; parent and publication review remains separate. Automatic
switching by sortie history or thermal state is outside this contract.

C03 retains the issue #18 business case: one formation mission requires two
aircraft, both aircraft start 30-minute preparation at 07:30, planned launch is
08:00, each preparation needs one member of the same personnel pool, and the
maximum launch delay is one hour. Staffing 2 should launch at 08:00; staffing 1
should launch at 08:30; staffing 0 must not launch and its native deadline or
cancellation result must be recorded rather than inferred.

## Contract files

| Case | Parent | Unique mechanism | Main native tables |
|---|---|---|---|
| B01 | A01 | Positive fixed pre-mission preparation | `MissionPreparation`, `MissionType` |
| B02 | B01 | Two strictly serial preparation steps | `Tasks`, `TaskBreakDown`, `SubTaskType` |
| B03 | B02 | Explicit cold/hot task-type recipes | `MissionPreparation`, `MissionType`, `TaskBreakDown` |
| C01 | B02 | Personnel specialty and required quantity | `Resource`, `TaskResource` or `SubTaskResource`, `ResourceAllocation` |
| C02 | C01 | Joint personnel and equipment demand | `SubTaskResource`, `ResourceAllocation` |
| C03 | C02 | Two-aircraft formation sharing one personnel pool | `MissionType`, `MissionPreparation`, `SubTaskResource`, `ResourceAllocation` |

B02 revision `1.0.1` uses a 60-minute notice period: notice at 07:00,
10-minute INSPECT and 20-minute SERVICE complete at 07:30, and planned launch
remains 08:00. The original `1.0.0` candidate used a 30-minute notice period
with a 45-minute scalar `MissionPreparation.DURN`; SIMLOX rejected it with
conversion error `#200` and produced a four-byte SXO. That input and hash remain
a failed immutable snapshot and must not be selected for native acceptance.

C01--C03 revision `1.0.1` binds every `ResourceAllocation.POINT` to the
selected `Control.APID` (`AIR_BASIC`). Their original `1.0.0` candidates used
`POINT=AIR-TYPE`; SIMLOX rejected all nine variants with conversion error
`#167`. Those inputs and hashes also remain immutable failed snapshots. This
mapping repair does not change C03's 07:30 notice, two-aircraft formation, or
staffing 2/1/0 business contract.

All business times are integer minutes from simulation start. Native inputs use
hours and must preserve the exact minute values after conversion. Stable
business IDs must survive JSON import, native conversion and JSON roundtrip.

## Acceptance order

1. Validate schema, references, units and the exact parent-to-child delta.
2. Import in a fresh native work directory and roundtrip every non-empty row.
3. Run once with deterministic durations and retain invocation, exit status,
   conversion log, SXI, SXO, ENLOG and raw result export.
   The frozen interactive runner requires a verified active Console or RDP
   session, rejects SSH/session-0, and leaves any existing SIMLOX window alone.
   Separately authorized SSH CLI collection needs a source-bound launch
   context; under the 2026-09-29 standard, complete CLI evidence may pass the
   declared behavior gate after independent review.
4. Bind full aircraft, mission, task, step and resource identities before
   comparing event times.
5. Resolve case, variant and candidate revision from the manifest. Failed or
   superseded revisions are never executable acceptance candidates.
6. Check request, wait, acquire, work, release, preparation completion and
   launch in causal order. Aggregate utilization alone is insufficient.
7. Replay independently from the sealed input. Record the first discrepancy.
8. Complete the source, parent, behavior, reproduction and limitation review
   before changing a case to reusable/published. Sample the GUI according to
   risk; a missing screenshot is not a uniform release blocker.

The native run may disprove an expected behavior. Preserve that result as a
counterexample and keep the case unverified; do not revise the expected ledger
after seeing output without issuing a new contract version.

## Evidence boundary

These contracts do not by themselves establish native behavior, GUI acceptance,
Python/Rust equivalence, J35/F35 equivalence or performance. B01 and B02 must
pass before a resource result is attributed to C01/C02. C01 and C02 must pass
before C03, and catalog-level C03 acceptance remains gated by A03.
Staffing/capacity variants differ only in the declared capacity field. Faults,
spares, PM, random durations, cancellation policy and cross-site resources are
outside this package.
