# SIMLOX air-support teaching cases

This library follows issue #18. The [SIMLOX 2017 progressive catalog v2](progressive-catalog-v2.md) has 108 planned case definitions: the original 26 business cases and 82 method, experiment and authoring extensions. Its 579 named variants and all 133 input tables are mapped to manual sources and acceptance plans. The catalog is a frozen planning snapshot; the separate [publication index](publication-index-v1.json) lists 28 accepted bounded CLI packages covering 22 distinct case IDs as of 2026-09-30. Each linked case report defines its precise scope and limits. Under the [revised acceptance standard](execution-plan-v2.md#3-证据状态和阶段门), source-bound CLI behavior evidence can support delivery and publication without a universal GUI gate. The aircraft is a generic teaching asset; real F35/J35 applications need separate contracts and evidence.

## Current implementation batch

The [staged execution plan](execution-plan-v2.md) assigns local parallel development and serialized native verification on 4700-3. The [preparation/resource batch](preparation-resource-v1/README.md) contains historical B01/B02/B03/C01/C02/C03 candidates; their later accepted packages and versions are listed below and in the publication index. B03 uses explicit cold-first/hot-sortie mission types; C03 uses two aircraft in one formation sharing personnel. The [delivery report](issue18-delivery-v2.md) separates implementation, local checks, native evidence and remaining gates. The [import source manifest](catalog-import-source-v2.json) records the original remote working-tree files before local revisions.

The [published B02 1.0.2 serial-preparation case](B02-serial-preparation-v1.0.2/README.md) derives from accepted B01 1.0.1 and has a separate source-bound native run, exact parent diff and independent raw replay. The older B02 1.0.1 batch candidate remains historical and is not its parent.

The [published B03 1.0.2 explicit cold/hot preparation case](B03-explicit-cold-hot-v1.0.2/README.md) derives directly from B02 1.0.2 and uses A02's signed repeated-wave scope. Its [native evidence](B03-explicit-cold-hot-v1.0.2/evidence-2026-09-29.md) and independent replay accept only the explicit `COLD-FIRST`/`HOT-SORTIE` mission-type recipes on one aircraft; automatic sortie-history switching remains unverified.

The [C01 1.0.2 personnel-capacity case](C01-personnel-capacity-v1.0.2/README.md) derives from published B02 1.0.2. Four source-bound CLI runs independently confirm a two-person crew lease, insufficient capacity, zero capacity and wrong specialty. Its [evidence report](C01-personnel-capacity-v1.0.2/evidence-2026-09-29.md) bounds the publication decision.

The [C02 1.0.2 joint-resource case](C02-joint-resources-v1.0.2/README.md) derives from accepted C01 capacity two. Four source-bound CLI runs compare joint P-CREW/E-GSE acquisition in one-step and two-step preparation, with equipment-zero controls. Its [evidence report](C02-joint-resources-v1.0.2/evidence-2026-09-29.md) records the exact source and raw hashes.

The [A02 repeated-wave sign-off](A02-single-aircraft-repeated-missions/cli-scope-signoff-2026-09-29.md) and [A03 two-aircraft sign-off](A03-two-aircraft-formation-v1.0.1/cli-scope-signoff-2026-09-29.md) publish bounded behavior from sealed earlier runs. The [C03 1.0.2 shared-crew formation case](C03-shared-crew-formation-v1.0.2/README.md) derives from published C02 and uses A03 as its formation prerequisite. Three source-bound native runs check parallel, serial and zero-capacity crew behavior; its [evidence report](C03-shared-crew-formation-v1.0.2/evidence-2026-09-29.md) bounds that publication.

The [C04 1.0.0 deadline and cancellation case](C04-deadline-cancellation-v1.0.0/README.md) derives directly from C03's published inputs. Five sealed CLI runs check crew readiness before/at/after the fixed cutoff, separate missing-aircraft and missing-crew conditions, partial-work cleanup and final stocks. The [evidence report](C04-deadline-cancellation-v1.0.0/evidence-2026-09-29.md) records independent replay and the failed, nonpublished horizon probe. The v2 machine catalog remains a planning snapshot; it is not rewritten as a publication register.

The [A09 1.0.1 nested-profile sign-off](A09-hierarchical-operation-profile-v1.0.1/cli-scope-signoff-2026-09-29.md) publishes one fixed four-wave CLI recipe from the accepted A02 parent. Its retained native run and separate 98-check read-only replay support only the tested `IQTY=2`, `IPER=48 h` profile; the general expansion formula and other A09 variants remain unverified.

The [A17 1.0.0 two-unit group sign-off](A17-multi-unit-group-v1.0.0/cli-scope-signoff-2026-09-29.md) publishes one fixed CLI recipe from the accepted A03 parent: one two-aircraft mission draws one aircraft from each of two explicit units at separate bases, then returns both. The sealed four-step run, 281-check author validation and independent read-only replay support this bounded behavior. Priority choice, implicit units, XTIME, transfer and other A17 variants remain unverified.

The [D01 1.0.0 restricted sign-off](D01-system-direct-repair-v1.0.0/cli-scope-signoff-2026-09-29.md) publishes the system-level direct-repair slice from accepted A02. A seeded native run observed two critical failures and 0.5-hour local repairs, with two mission aborts, one successful mission and terminal recovery. The 293-check author replay and separate read-only review passed. A separate [D01 installed-LRU sign-off](D01-installed-lru-direct-repair-v1.0.0/cli-scope-signoff-2026-09-29.md) subsequently accepted one installed-item failure, local spare replacement, failed-item direct repair and stock return. [E01–E05 and E04 variants](capabilities.md) add bounded physical replacement, local backorder, shared spare, upstream transport and repair-loop behavior.

The [D03 1.0.0 calendar-PM sign-off](D03-calendar-pm-v1.0.0/cli-scope-signoff-2026-09-30.md) adds two nonconflicting one-hour PM services to A02's three-mission aircraft: 24–25 and 49–50 hours in a sealed 60-hour run. The second start follows the first completion by 24 hours in this run. The 62-check author replay and independent 19-check review passed. Conflict, resource and alternative-counter PM behavior remain separate catalog scopes.

The [D04 1.0.0 operation-hour PM sign-off](D04-flight-hour-pm-v1.0.0/cli-scope-signoff-2026-09-30.md) changes D03's trigger to three `OPHOURS`: a two-hour mission at 8–10 and a one-hour mission at 40–41 bracket a 30-hour no-flight interval; one-hour PM follows at 41–42. The 65-check author replay and independent 22-check raw review passed. No PM occurred during the long gap. Other PM counters and conflict behavior remain separate scopes.

The [D05 1.0.0 bounded competition sign-off](D05-maintenance-competition-v1.0.0/cli-scope-signoff-2026-09-30.md) combines one observed critical direct repair, two noncritical calendar PM jobs, and one shared worker. The repair holds that worker 23–28; the PM subtasks then perform 28–29 and 29–30, while a later mission succeeds. Author 81-check and independent 51-check raw replays passed. This is one restricted D05 priority slice; other priority and capacity combinations remain planned.

The [D05.var01 two-worker control](D05-var01-two-workers-v1.0.0/cli-scope-signoff-2026-09-30.md) changes only `ResourceAllocation.RQTY=1→2` plus labels from that accepted input. The same failure and missions occur, but healthy-aircraft PM work overlaps repair 24–25 and measured worker wait drops from five to zero hours. The 113-check author pair replay and independent 63-check raw replay passed. Zero-worker capacity and other priority boundaries remain planned.

The [D13.var02 static MAXPM comparison](D13-var02-maxpm-two-v1.0.0/cli-scope-signoff-2026-09-30.md) derives two aircraft from D03 with a noncritical calendar-PM window. Both PM task objects start at hour 24, while performed one-hour subtasks are serial under `MAXPM=1` and parallel under `MAXPM=2`. The 104-check author pair replay and independent 35-check raw review passed. D13's activation-period, dynamic-capacity and critical-PM boundaries remain planned.

## Find and reproduce

- [Progressive catalog v2 / 渐进案例目录](progressive-catalog-v2.md): learning path, every case, minimal configuration and acceptance targets.
- [Machine catalog v2](catalog-v2.json): mechanism, prerequisites, planned variants and unchanged evidence status.
- [Publication index](publication-index-v1.json): accepted bounded CLI packages and their case-level sign-offs; this is the live publication overlay for the frozen planning catalog.
- [Manual coverage](manual-coverage-v2.json) and [source fingerprints](manual-sources-v2.json): methods, table/field references, section coverage and local source retrieval.
- [Frozen catalog v1](catalog.json): original 26-case evidence index; retained for A01/A02 provenance. `tools/build_catalog.py` rebuilds this v1 index only.
- [Capabilities](capabilities.md): what is actually supported by local evidence.
- [A01](A01-single-aircraft-single-mission/README.md) and [A02](A02-single-aircraft-repeated-missions/README.md): contracts, mappings, expected timelines, immutable evidence.
- [Pairing contract](pairing-contract.json): minimal interface for AMD128; cross-engine status is unverified.
- [Known issues](known-issues/README.md): native configuration mistakes, output mapping and unresolved J35 contracts.

`native-schema.json` is a row-free table layout derived from the SHA-locked phase6 native JSON. It includes table/column names and datatypes, not source model rows. `tools/generate_native.py` builds checked `native-input.json` files from case parameters. It is a native SIMLOX table writer, not a second `spare_mvp` Project JSON interpreter. `tools/diff_native.py` proves A02 adds only two OperationProfile rows.

The original A01/A02 large raw evidence lives on 4700-3 under `repo/data/local/simlox-case-library/v1/<case-id>/<immutable-run-id>/`, which Git ignores. Later cases keep sealed native outputs under their own ignored `runs/<immutable-run-id>/` directories; case sign-offs name the run ID, raw hashes and retrieval path. Original exports remain byte-for-byte; report parsing normalizes the native writer's trailing commas only in memory or a separate derived artifact.

The recent D/E case runners used for the source-bound native runs refuse an existing run directory, use session-0 SSH and the host-wide `Global\SimloxIssue18NativeQueue` mutex, and guard the preserved GUI PID 13340 identity and active session before and after each hidden CLI step. They bind executable, input, parent, contract, builder, checker and runner hashes before execution; closure hashes all raw outputs. Earlier A01/A02 runner behavior is documented in those packages. On this host native execution succeeds from the coordinator's SSH PowerShell context; direct Codex child processes previously returned exit 0 without artifacts. The task-local runner retains the verified native working directory. Do not invoke parallel native batches or close the user's GUI.

Publication review found false positives in the first validator. The corrected
`tools/run_native_bound.ps1` writes `invocation.json` **before** the first native
process, including the case/run/input, schema, contract, parameters, generator,
validator, runner, binding module, executable and working-directory hashes or
identities. After import/export/calc/report it writes `closure.json` with exact
raw-artifact hashes and the invocation SHA. `tools/validate_native.py` requires
both bindings, verifies every artifact and step, then checks full aircraft and
mission-instance event identities and each 30-minute system-state interval.
Old runs can be reanalysed read-only with `--legacy-read-only`; they cannot gain
new acceptance attribution. The corrected collection-window analysis is
`collection-window-review-v2.json`, derived from unchanged old raw evidence.

## Publication gate

The earlier A01/A02 final and replay runs passed historical CLI checks but lack
pre-run binding. Four new normal/replay runs have independent invocation IDs,
sealed raw files and strict read-only validation passes. They restore CLI
behavior acceptance for these two teaching cases. GUI observations have since
been recorded separately in the [dated addendum](gui-acceptance-2026-09-29.md).
GUI completeness no longer controls publication; GUI is sampled when useful,
and screenshot retention is optional. Each case still needs a
case-level review of its declared behavior, required parent behavior, raw
evidence, reproducibility and limitations before `reusable_published` is set.
No case status is changed merely by this policy revision. A mapped manual
method or a passing catalog check does not establish native behavior. See the
[manual review findings](known-issues/manual-review-v2.md) for capability
probes and conflicting source descriptions.
