# Domain profile generality v1

Registered profiles load from their own canonical schema. The aircraft-support-v1
pack is unchanged: the same admitted Business sections, the same lowering, and
the same `58bc6d1a…` B1 fingerprint. A canonical document whose schema is not
registered is rejected. A registered non-aircraft schema never enters the
aircraft importer, so it does not receive default tails, nodes, or activities.

Unknown Business section names, and unknown `$root` properties, fail validation
with `unconsumed_business_section`, a source path, and a message naming the
profile. Missing admitted aircraft sections still use the historical defaults.
A queue-shaped payload labeled `aircraft-support-v1-input-v1` fails on
`business.sections.arrivals`.

## Restricted queue profile

`multi-server-queue-v1` is a restricted domain profile, not a general queue
algebra and not an aircraft compatibility operation. The admitted range is:

- exactly two servers
- Poisson arrivals and exponential service
- one non-preemptive priority rule ordered by priority, arrival time, then customer id
- lowest-index idle server
- metric set exactly `mean_wait`
- horizon 1..=10080 minutes, finite rates in `(0, 1e6]`, and `rate * horizon <= 10000`
- at most eight classes
- fixed limits of 10000 admitted arrivals and 100000 loop steps

Mean wait is the sequential IEEE-754 sum of `(service_start - arrival)` for
customers who start service at or before the horizon, divided by that count.
Customers still waiting are excluded. Service that would finish after the
horizon is not completed. Random streams are `cpython-mt19937-v1` and use stable
ids `interarrival:customer-NNNN`, `class:customer-NNNN`, and
`service:customer-NNNN`. Python and the Rust runtime share that call order.
Product `run` and `batch` execute the plan in Rust.

Trace query admits `python-reference` and `rust-runtime` for aircraft
`legacy-minute-v1` and for this queue profile. `event-time-v2` stays
unadmitted for both backends. Queue design links require a full bundle that
recompiles to the queried plan. Queue events have no stable event id.

## Limits

- `diff_runs` remains the aircraft run-record contract.
- Queue run identity is `multi-server-queue-run-identity/v1`, not the aircraft run-identity contract.
- Execution provenance stays caller-asserted.
- One server, three or more servers, other disciplines, and other metrics are rejected.
- The queue runtime is selected by plan version at the artifact boundary. It does not extend the aircraft phase interpreter.
