# SIMLOX air-support teaching cases

This library follows issue #18. The [SIMLOX 2017 progressive catalog v2](progressive-catalog-v2.md) has 108 planned case definitions: the original 26 business cases and 82 method, experiment and authoring extensions. Its 579 named variants and all 133 input tables are mapped to manual sources and acceptance plans. The catalog is a planning snapshot; later A03, A09 and B01–C03 CLI evidence is recorded in case-specific reports. Under the [revised acceptance standard](execution-plan-v2.md#3-证据状态和阶段门), source-bound CLI behavior evidence can support delivery and publication without a universal GUI gate. The aircraft is a generic teaching asset; real F35/J35 applications need separate contracts and evidence.

## Current implementation batch

The [staged execution plan](execution-plan-v2.md) assigns local parallel development and serialized native verification on 4700-3. The [preparation/resource batch](preparation-resource-v1/README.md) implements B01/B02/B03/C01/C02/C03 candidates. B03 uses explicit cold-first/hot-sortie mission types; C03 uses two aircraft in one formation sharing personnel. The [delivery report](issue18-delivery-v2.md) separates implementation, local checks, native evidence and remaining gates. The [import source manifest](catalog-import-source-v2.json) records the original remote working-tree files before local revisions.

The [published B02 1.0.2 serial-preparation case](B02-serial-preparation-v1.0.2/README.md) derives from accepted B01 1.0.1 and has a separate source-bound native run, exact parent diff and independent raw replay. The older B02 1.0.1 batch candidate remains historical and is not its parent.

The [published B03 1.0.2 explicit cold/hot preparation case](B03-explicit-cold-hot-v1.0.2/README.md) derives directly from B02 1.0.2 and uses A02's signed repeated-wave scope. Its [native evidence](B03-explicit-cold-hot-v1.0.2/evidence-2026-09-29.md) and independent replay accept only the explicit `COLD-FIRST`/`HOT-SORTIE` mission-type recipes on one aircraft; automatic sortie-history switching remains unverified.

The [C01 1.0.2 personnel-capacity case](C01-personnel-capacity-v1.0.2/README.md) derives from published B02 1.0.2. Four source-bound CLI runs independently confirm a two-person crew lease, insufficient capacity, zero capacity and wrong specialty. Its [evidence report](C01-personnel-capacity-v1.0.2/evidence-2026-09-29.md) bounds the publication decision.

The [C02 1.0.2 joint-resource case](C02-joint-resources-v1.0.2/README.md) derives from accepted C01 capacity two. Four source-bound CLI runs compare joint P-CREW/E-GSE acquisition in one-step and two-step preparation, with equipment-zero controls. Its [evidence report](C02-joint-resources-v1.0.2/evidence-2026-09-29.md) records the exact source and raw hashes.

The [A02 repeated-wave sign-off](A02-single-aircraft-repeated-missions/cli-scope-signoff-2026-09-29.md) and [A03 two-aircraft sign-off](A03-two-aircraft-formation-v1.0.1/cli-scope-signoff-2026-09-29.md) publish bounded behavior from sealed earlier runs. The [C03 1.0.2 shared-crew formation case](C03-shared-crew-formation-v1.0.2/README.md) derives from published C02 and uses A03 as its formation prerequisite. Three source-bound native runs check parallel, serial and zero-capacity crew behavior; its [evidence report](C03-shared-crew-formation-v1.0.2/evidence-2026-09-29.md) bounds that publication.

The [C04 1.0.0 deadline and cancellation case](C04-deadline-cancellation-v1.0.0/README.md) derives directly from C03's published inputs. Five sealed CLI runs check crew readiness before/at/after the fixed cutoff, separate missing-aircraft and missing-crew conditions, partial-work cleanup and final stocks. The [evidence report](C04-deadline-cancellation-v1.0.0/evidence-2026-09-29.md) records independent replay and the failed, nonpublished horizon probe. The v2 machine catalog remains a planning snapshot; it is not rewritten as a publication register.

The [A09 1.0.1 nested-profile sign-off](A09-hierarchical-operation-profile-v1.0.1/cli-scope-signoff-2026-09-29.md) publishes one fixed four-wave CLI recipe from the accepted A02 parent. Its retained native run and separate 98-check read-only replay support only the tested `IQTY=2`, `IPER=48 h` profile; the general expansion formula and other A09 variants remain unverified.

The [A17 1.0.0 two-unit group sign-off](A17-multi-unit-group-v1.0.0/cli-scope-signoff-2026-09-29.md) publishes one fixed CLI recipe from the accepted A03 parent: one two-aircraft mission draws one aircraft from each of two explicit units at separate bases, then returns both. The sealed four-step run, 281-check author validation and independent read-only replay support this bounded behavior. Priority choice, implicit units, XTIME, transfer and other A17 variants remain unverified.

The [D01 1.0.0 restricted sign-off](D01-system-direct-repair-v1.0.0/cli-scope-signoff-2026-09-29.md) publishes only the system-level direct-repair slice from accepted A02. A seeded native run observed two critical failures and 0.5-hour local repairs, with two mission aborts, one successful mission and terminal recovery. The 293-check author replay and separate read-only review passed. Installed-item failure, replacement, stock and ItemRepair remain unverified D01 extensions.

## Find and reproduce

- [Progressive catalog v2 / 渐进案例目录](progressive-catalog-v2.md): learning path, every case, minimal configuration and acceptance targets.
- [Machine catalog v2](catalog-v2.json): mechanism, prerequisites, planned variants and unchanged evidence status.
- [Manual coverage](manual-coverage-v2.json) and [source fingerprints](manual-sources-v2.json): methods, table/field references, section coverage and local source retrieval.
- [Frozen catalog v1](catalog.json): original 26-case evidence index; retained for A01/A02 provenance. `tools/build_catalog.py` rebuilds this v1 index only.
- [Capabilities](capabilities.md): what is actually supported by local evidence.
- [A01](A01-single-aircraft-single-mission/README.md) and [A02](A02-single-aircraft-repeated-missions/README.md): contracts, mappings, expected timelines, immutable evidence.
- [Pairing contract](pairing-contract.json): minimal interface for AMD128; cross-engine status is unverified.
- [Known issues](known-issues/README.md): native configuration mistakes, output mapping and unresolved J35 contracts.

`native-schema.json` is a row-free table layout derived from the SHA-locked phase6 native JSON. It includes table/column names and datatypes, not source model rows. `tools/generate_native.py` builds checked `native-input.json` files from case parameters. It is a native SIMLOX table writer, not a second `spare_mvp` Project JSON interpreter. `tools/diff_native.py` proves A02 adds only two OperationProfile rows.

Large raw evidence lives on 4700-3 under `repo/data/local/simlox-case-library/v1/<case-id>/<immutable-run-id>/`, which Git ignores. To retrieve locally: `Get-ChildItem -Recurse -LiteralPath 'C:\Users\user\Documents\Codex\2026-09-27\simlox-case-library-a01-a02-v1\repo\data\local\simlox-case-library\v1'`. Each case evidence index lists exact run paths and SHA-256. Original exports remain byte-for-byte; the native report's trailing commas are normalized into `report-normalized.json` with both raw and derived hashes.

The runner refuses existing run directories and any active SIMLOX process. It checks the executable and input SHA, verifies import/export nonempty business rows, conversion errors, SXI/SXO size, parsed report and ENLOG before acceptance. On this host native execution has succeeded from the coordinator's SSH PowerShell launch context; direct Codex child processes had returned exit 0 without artifacts. The task-local runner retains the previously successful native working directory. Do not invoke parallel native batches or close a user's GUI.

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
