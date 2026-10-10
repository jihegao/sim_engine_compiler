# Workload counters and interpretation

All counters below belong to one profiled sample, never a sum inferred for the
formal three-sample batch. Profile times are excluded from performance ratios.
The runtime counter definitions are in `rust/runtime/src/runtime.rs`.

| Field (`resource_dispatch_` prefix unless stated) | Meaning |
|---|---|
| `phase_calls` | Dispatch phase invocations |
| `waiting_jobs_observed` | Sum of waiting-set length at phase entry; exposure, not unique jobs |
| `waiting_job_indexes_peak` (no prefix) | Maximum observed active waiting-set size |
| `candidate_visits` | Outer scan visits, or actual candidate dispatch visits |
| `replay_visits` | Additional full-observation delay-event replay visits |
| `guard_evaluations` | Executed resource guards |
| `cache_hits` | Reused blocked-resource results |
| `index_lookups` | Reverse dependency keys probed after changes |
| `index_candidate_visits` | Static dependency rules traversed |
| `index_waiter_visits` | Waiting instances traversed in matching activity/step buckets |
| `waiting_index_updates` | Waiting-state add/remove transitions; not every allocation/set instruction |
| `sort_items` | Items submitted to the scan arm's stable sort |
| `merge_inputs` | Candidate/replay/invalidation items offered to the ordered candidate set |
| `merge_insertions` | Unique successful inserts into that set |
| `queue_updates` | Waiting-job invalidation notifications |
| `queue_ns` | Queue construction/sort and in-phase invalidation merge timing only |
| `event_attempts` | Trace-event attempts in resource-dispatch phase |

Global `trace_events_attempted` and `trace_events_materialized` distinguish
business/diagnostic emission attempts from retained JSON events. O5 calendar
push/pop/wakeup counters are scheduling diagnostics; they are not interchangeable
with trace-event counts. Summary intentionally materializes no trace. Profile
admission compares each profiled result against its unprofiled result.

The scan and cache arms still visit/sort the complete waiting set. Candidate
mode maintains reverse buckets and an ordered BTreeSet; its queue cost depends
on offered/merged candidates and its resource-change work depends on affected
buckets. Full-mode replay may revisit the broad waiting set. Consequently guard
reduction alone proves neither less outer work nor an asymptotic improvement.
Use candidate+replay visits together, plus reverse-index traversal and maintenance.
Counters do not cover allocations, every hash/set operation, or individual
comparison counts inside sorting. Formal end-to-end cost includes them.

Synthetic low contention increases resources with fleet size. Dense contention
holds one shared capacity pool fixed. Sparse contention increases independent
resource buckets and staggers their releases. Each has a common bounded horizon,
but model/network size is intentionally different across families. The 4/16/64
points support a bounded structural explanation, not a general complexity proof.
