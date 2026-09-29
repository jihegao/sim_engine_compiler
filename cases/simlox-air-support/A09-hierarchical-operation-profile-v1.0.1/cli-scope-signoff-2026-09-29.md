# A09 1.0.1: bounded nested-profile CLI sign-off, 2026-09-29

## Decision and source

`native_behavior_accepted_cli_scope` and `reusable_published` apply to the
tested two-level `OperationProfile` only: one aircraft, root `IQTY=2` and
`IPER=48 h`, child starts at relative hours 8 and 20, four fixed two-hour
missions during a 48-hour horizon. This later review leaves the frozen
`1.0.1-candidate` contract, input, original run, and historical status fields
unchanged. It publishes the observed recipe, not an `IPER/IQTY` expansion
formula or all A09 catalog variants.

The accepted parent is [A02 1.0.0's repeated-wave CLI scope](../A02-single-aircraft-repeated-missions/cli-scope-signoff-2026-09-29.md),
input SHA-256 `84c5cca6c06384b850d2420297a3f5c2f5c553904f123f690190fdb42475e0b8`.
The [A09 contract](contract.json) SHA-256 is
`0eec62204ba6a47509dba5cbfd86bad4908d06b2cdd9f3770ef3d1bb26610874`;
the [checked native input](native-nested.json) SHA-256 is
`e795c5fcf563f8e42ab9e9cb161a925bec3b06157cbbecde7901e99bfec91d85`.
The [independent replay](review/independent-readonly-2026-09-29.json) confirmed
the A02-to-A09 table diff in the v1.0.0 candidate and the single root
`OperationProfile.IPER` change from 24 to 48 hours in v1.0.1. The failed
v1.0.0 nested run remains a separate, unpublished counterexample.

The source method is `M-A09`, SIMLOX 2017 User's Reference physical PDF pages
270–276. Its installed PDF SHA-256 is
`39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`
as recorded in [manual-sources-v2.json](../manual-sources-v2.json). The cited
mapping identifies nested profile references and hour-valued fields; it does
not establish a general repetition rule.

## Sealed native result

The original session-0 SSH run ID is `a09-v101-20260929-01`, stored at
`C:\Users\user\Documents\Codex\2026-09-29\simlox-a09-v101-ed46e1c02e64\repo\cases\simlox-air-support\A09-hierarchical-operation-profile-v1.0.1\runs\a09-v101-20260929-01`.
Its invocation SHA-256 is
`7188ce95ef841c5b4c13a132a1ac93ee947239db002b227e21af4202a87a1892`;
closure SHA-256 is
`8f09c55a929286d55fd872d9e635be98aa8289bb61ecf25e1eb20e608cded942`.
The closure indexes all 11 raw files by byte length and SHA-256. In
particular, `model.sxi` is
`941086de17e0800cf34cffadfe45e938c0df9a585421ee2f5d5e4a18432a97df`,
`model.sxo` is
`8b825f5ef87c4a212dcd34bfe4b7021631dc50ffa180cb5a67741c5462740b93`,
`model.log` is
`c87d12ebe855b1a4c6e987318b2ea247ced02d76b25d676d707b6c42588b9ba6`,
and `report-raw.json` is
`36cd362bb15e70e388c77885143a359a6d78a4204aa63bbcabf29943c0d618b6`.
The source bundle SHA-256 is
`ed46e1c02e642996db41ed5bb608522a9ce19f071d3b3761c58f7446f02783ac`.

Import, export, calculation, and JSON report commands each exited zero.
The native conversion had zero errors, with warnings 108 and 126 explained
by the inherited A02 `ENLOG=Y` and row-free `System.FRT=0` configuration.
Ten operating business tables roundtripped unchanged. The native log records
four distinct mission instances ordered at hours 7/19/31/43, started at
8/20/32/44, and completed at 10/22/34/46, with no cancellation or abort.
The aircraft readiness events close each mission. The result report has 96
contiguous half-hour intervals, eight aircraft-hours of operation, the
expected ready and allocation profiles, and zero preparation work. Its raw
log and report bytes equal the previously passed flat control's bytes.
The report contains a trailing comma; the original byte hash is preserved,
and parsing normalization is confined to the read-only check.

The [separate reviewer](review/independent_readonly.py) used only Python's
standard library and imported none of the author's code. Its
[98-check replay](review/independent-readonly-2026-09-29.json) passed with
zero differences and five in-memory negative controls. The reviewer script
SHA-256 is `00a6659aff1d17fe22ce395d1514aef65205b29aedfe58146e81a0520b804061`;
its report SHA-256 is
`d6fea0a687141c40fa8c1e0bce08594384dec437bfd9d3b35b95cbe3111ca2a0`.
The separate [GUI observation](gui-review-2026-09-29.md) checked the two
profile levels and selected charts from hash-identical SXI/SXO copies. It is
partial; no unobserved GUI function is accepted. GUI PID 13340 stayed present.

## Reproduction and limits

On 4700-3, run `python review/independent_readonly.py` from this case
directory to replay the original sealed evidence. To generate a new native
run, first check `python build.py`, then invoke `run_native_ssh.ps1` with a
fresh `-RunId` from the verified session-0 SSH context, serially under the
host-wide queue. Use `-AllowExistingGui` only while the same interactive GUI
is active. The runner refuses reused IDs and changed fingerprints. Its
absolute raw path and pinned executable environment are recorded above and
in the invocation; no raw native files are checked into Git.

This acceptance covers no random timing, other quantities or periods,
duplicate profile rows, malformed nested references, faults, preparation,
resource or inventory behavior, general same-time priority, GUI-only
behavior, cross-engine equivalence, or performance. The v1.0.0 nested
candidate's extra hour-19 notification and cancellation remain a recorded
failure of that four-wave contract. Catalog v2 remains a planning snapshot;
this dated sign-off is the bounded publication decision.
