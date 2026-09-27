# Independent three-arm workload-counter review

Status: complete, read-only post-window review. No simulation, profile, test, or
timing process was rerun for this analysis.

Source commit: `cf50eec2f9fdf1ac76e3d292e8b42b6f33f98b38`

Evidence bindings:

- admission gate (60/60 profile records):
  `64a226c83290252c91cef2788b50552b4e7677ec5db0506e15538b544a04d1fa`
- formal summary (99/99 cells):
  `948430e8efb6712b85b82e0295020a2478c86786400ec42573056cc1f5a5e2f5`
- formal manifest:
  `17ea2b74527eda5029dc0b9d476ac073581136c67ed27f4f8331523b39a5a38e`
- IR-reuse manifest:
  `a84903ff636286650c2b485de80d2cc3df862970b978fe2df66c39994962f928`

The table below uses the admission seed-0 diagnostic profiles. `wait` is the
sum of waiting-set sizes observed at resource-dispatch phase entry. `guards`
are real guard evaluations. `replay(full)` is the full-observation replay work
needed to preserve every capacity-delay event. `idx-waiter` is the number of
waiting jobs traversed after reverse-index hits. `merge` shows summary/full
candidate-queue inputs. Profile timing fields are excluded; performance
classification comes only from the separate unprofiled formal window.

| case | wait | scan guards | cache guards | candidate guards | guard reduction vs scan | replay(full) | idx-waiter | merge summary/full |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| low N4 | 8 | 8 | 8 | 8 | 0.00% | 0 | 40 | 32 / 32 |
| low N16 | 32 | 32 | 32 | 32 | 0.00% | 0 | 544 | 512 / 512 |
| low N64 | 128 | 128 | 128 | 128 | 0.00% | 0 | 8,320 | 8,192 / 8,192 |
| sparse N4 | 18 | 18 | 18 | 12 | 33.33% | 6 | 32 | 20 / 26 |
| sparse N16 | 60 | 60 | 60 | 40 | 33.33% | 20 | 208 | 136 / 156 |
| sparse N64 | 432 | 432 | 432 | 160 | 62.96% | 272 | 832 | 544 / 816 |
| dense N4 | 32 | 32 | 32 | 20 | 37.50% | 12 | 64 | 44 / 56 |
| dense N16 | 192 | 192 | 192 | 100 | 47.92% | 92 | 384 | 284 / 376 |
| dense N64 | 960 | 960 | 960 | 484 | 49.58% | 476 | 1,920 | 1,436 / 1,912 |
| J35 | 4,617 | 4,617 | 3,948 | 4,010 | 13.15% candidate; 14.49% cache | 0 | 21,082 | 11,804 / 11,804 |

## Structural findings

1. The low-contention curve is an adverse topology for candidate dispatch.
   It eliminates no guards at any size. Reverse-index waiter traversal grows
   from 40 to 544 to 8,320, while merge inputs grow from 32 to 512 to 8,192.
   At N64 the candidate arm avoids sorting 128 items but performs 8,320 indexed
   waiter visits and 8,192 merge offers. This provides a structural explanation
   consistent with the unprofiled candidate regression rather than supporting
   adoption.

2. The staggered sparse family demonstrates bounded semantic selectivity.
   Candidate guards fall 33.33%, 33.33%, and 62.96% at N4/N16/N64. At N64,
   `idx-waiter / wait = 832 / 432 = 1.926`, below dense N64's `2.000` and far
   below low N64's `65.000`. This is evidence that releases target small
   dependency buckets. It is not an asymptotic claim: the ratios are
   non-monotonic across the three bounded scale points, and the remaining
   index/merge maintenance is material.

3. Dense contention reduces true guards but retains broad invalidation work.
   Candidate guards approach half of scan at N64 (484 versus 960). In full
   observation, 476 replay visits restore every omitted delay event, so
   `candidate + replay = 960`, exactly the scan outer workload. Summary removes
   those replay events and attempts 589 trace events versus 1,065 in full, but
   still performs 1,920 indexed waiter visits and 1,436 merge offers.

4. Full and summary have identical scan/cache counters. Candidate true guard
   counts also match across observation levels. For affected synthetic cases,
   the full-minus-summary event-attempt difference equals replay count exactly:
   sparse N64 `1,313 - 1,041 = 272`; dense N64
   `1,065 - 589 = 476`. This separates trace-contract replay from scheduling
   selectivity rather than crediting output pruning as an algorithm gain.

5. J35 shows only a modest hot-path reduction with high maintenance. Cache
   avoids 669 guards (14.49%); candidates avoid 607 (13.15%) and do not require
   replay. The candidate arm also records 8,818 index lookups, 202,770 dependency
   rule visits, 21,082 indexed waiter visits, and 11,804 merge inputs while
   eliminating the scan arm's 4,617 sort items. These counters are consistent
   with the formal negative result and suggest that maintenance and larger-plan
   costs can offset saved guards. No per-operation cost attribution was
   measured.

## Formal performance relationship

The counter explanation agrees with the unprofiled window, but does not replace
it. Every cache-versus-scan and candidate-versus-scan group was classified as a
regression. J35 summary candidate/scan median paired ratios were 1.1628
execution, 1.1818 end-to-end, and 1.1514 RSS; J35 full ratios were 1.2729,
1.1197, and 1.0468. No tested structural point demonstrated default-adoption
benefit. Candidate dispatch should remain explicit opt-in; the historical #9
threshold and default state should remain unchanged.

## IR reuse evidence

The reuse manifest binds one synthetic canonical origin
`63b3f8b6828eda3e6ca6e20bacedbd716795c48d72ec802e8153fe8a1e52ed08`
to six persisted revisions: mission frequency, resource counts, and process
composition under both `legacy-minute-v1` and `event-time-v2`. Each revision has
distinct Business/Core/Plan fingerprints and explicit edited Business paths.
Legacy revisions include independent seed-0 Python reference results;
event-time Python reference remains explicitly unsupported. The commit-bound
`ir-reuse` receipt passed the exact three-Rust-arm differential suite, including
cross-profile business/RNG fields, full/summary observation, repeated seeds,
thread-count invariance, and regenerated dependency indexes. This establishes
model/IR reuse for the three bounded dimensions without per-variant Rust
scheduler edits. It does not establish J35 provenance for the synthetic cases
or a default optimization win.

## Limits

- Diagnostic profiles are one seed-0 run per case/arm/observation and are used
  only for workload counts, not timing.
- Only N4/N16/N64 and the frozen J35 object were measured.
- The three formal seeds are independent trajectories, not statistical power
  for a general workload population.
- Queue nanoseconds and instrumented execution timing are intentionally absent
  from this conclusion because instrumentation can perturb timing.
