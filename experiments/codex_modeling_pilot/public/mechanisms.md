# Public mechanism cards

These are reusable mapping aids for `aircraft-bounded-events/v1`. Read the schema
guide for complete exact fields. Values below are independent illustrative
examples, not experiment task parameters. Only supported mechanisms may compose;
unsupported behavior must be reported rather than approximated silently.

## Formation and exclusive ownership

**Need:** a mission requires a complete group of matching aircraft.

**Mapping:** `missions[].requirements = {"scout": 3}` and aircraft `type:"scout"`.
Use `start_hours`, `notice_hours`, `duration_hours`, and `delay_hours` from the
requirement. Allocation may occur at notice, before launch. Aircraft become
exclusive to the mission while waiting/flying. Stable row order selects among
eligible aircraft; mission priority uses ascending integers then row order.
All members prepare individually through the selected process. No partial
formation launches. Return or cancellation releases ownership.

**Composition warning:** priority chooses mission allocation order; it is not a
general preemption policy. Dependencies delay launch but do not stop preparation.

## Reusable resource with atomic acquisition

**Need:** preparation consumes limited personnel/equipment capacity.

**Mapping:** a resource `{"id":"demo-team","capacity":3}` and a step with
`"demands":{"demo-team":2}`. Multiple resource demands in one step acquire
atomically, then release at completion or cancellation. Competing preparation
jobs wait FIFO in their creation order; blocked work does not exceed capacity.

**Composition warning:** resource constraints here belong to preparation steps.
There is no resource field for PM or direct repair. Do not rename repair as
preparation if that would change triggering, state, or scheduling semantics.

## Serial preparation with explicit steps

**Need:** preflight inspection precedes equipment loading.

**Mapping:** order the process `steps` list, for example `inspect` of 0.15 hours
then `load` of 0.35 hours. Each may have its own resource demands. `scalar_hours`
is also authored: it determines the early feasibility cutoff even when explicit
steps determine actual duration. An empty step list uses scalar-only work.

**Composition warning:** steps are serial per aircraft; different aircraft may
prepare concurrently within capacity. There is no arbitrary step DAG or parallel
fork inside one preparation process in this profile.

## Successful mission dependency

**Need:** a later mission must await successful return of an earlier one.

**Mapping:** set `depends_on:["demo-survey"]` on the later mission. This is a
launch prerequisite, not a fixed numerical delay. Supply both missions with
their own notice/start/tolerance/process. A predecessor's aborted return does
not satisfy the condition. Cycles reject.

**Composition warning:** if the dependency cannot be met before the later
mission's cutoff, normal cancellation follows. Do not encode a guessed success
time in place of the dependency.

## Calendar or flight-exposure maintenance

**Need:** maintenance after elapsed calendar time or accumulated flight time.

**Mapping:** an aircraft PM object such as
`{"id":"demo-pm","clock":"flight","interval_hours":3.5,"duration_hours":0.4}`.
Use `calendar` for elapsed calendar time. Calendar starts at zero and resets at
PM completion. Flight exposure accumulates over actual flights, including
aborted flights, and is inspected at return. PM needs a free landed aircraft.

**Composition warning:** only one PM clock per aircraft is expressible. A due
obligation survives repair; pending PM begins when repair finishes. Do not
replace a flight threshold with a fixed timestamp, or claim an OR of two clocks.

## Cutoff cancellation and stale-event invalidation

**Need:** release aircraft/resources when launch is no longer possible.

**Mapping:** author start, delay, process scalar, aircraft count and resource
capacity. Built-in early feasibility checks happen at
`max(notice, start + delay - scalar)`; incomplete allocation or impossible total
capacity cancels then. Temporary occupancy can wait until final cutoff at
`start + delay`. Still-unlaunched missions then cancel.

**Composition warning:** early checks do not estimate every remaining work
duration. Cancellation invalidates old work completion tokens, releases only
owned leases, and wakes other jobs. Completion at a cutoff precedes cancellation
and can permit launch. No explicit arbitrary `cancel` external event exists.

## Explicit external fault with direct repair

**Need:** study response to a stipulated fault time without sampling faults.

**Mapping:** `rng_profile:"external-events/v1"`, aircraft
`repair_mode:"direct"`, explicit `repair_hours`, and an external driver such as
`{"id":"demo-fault","time_hours":2.35,"operation":"fault","aircraft":"demo-aircraft","node":null,"item":null,"value_hours":0}`.
The target must be healthy and flying at that time. Fault aborts the mission
outcome; scheduled return remains. Repair begins after landing and restores
availability after the configured duration, subject to already-pending PM.

**Composition warning:** no random draws occur; this is response modeling,
not native failure generation. `damaged_arrival` ends a single-aircraft flight
immediately and requires direct repair. These two driver semantics differ.

## Physical spare and replacement repair

**Need:** removal, spare acquisition, fitting, repair and transport conserve
physical item identities.

**Mapping:** set `repair_mode:"replacement"`; specify installed item, stock and
repair nodes, remove/fit/item-repair durations. Put spare IDs in node `items`.
For distinct nodes provide both directed routes with transport durations.
Fitting waits for removal and spare arrival. Failed items travel to repair and
return into stock; all items have a single explicit location.

**Composition warning:** `in_transfer` adds a specified new physical item once.
There is no automatic reorder threshold. Never duplicate one item identity to
represent quantities, and do not model consumable inventory as capacity.

## Clarification and capability checks before composition

Determine whether required numerical values or rule choices are missing. Ask
focused questions naming the affected field instead of choosing arbitrary
defaults. If the semantics exceed the profile (native random fault distribution,
repair-resource scheduling, general preemption, multiple PM clocks, arbitrary
live state editing), return `unsupported` with the precise gap. A model that
compiles but omits a required mechanism is not a valid solution to the task.
