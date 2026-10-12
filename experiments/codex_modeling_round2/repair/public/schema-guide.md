# Public schema guide: bounded aircraft modeling pilot

This public guide describes an existing restricted aircraft profile. It contains
no assessment answers. Generate a JSON candidate; do not author Core, Plan,
runtime code, or new operations. The harness uses the existing canonical importer
and persists/reloads Business → Core → Plan before the Python reference run.

## Submission envelope

Exactly five keys are required; extra keys reject:

| Key | Value |
|---|---|
| `task_id` | Copy the public task's ID exactly. Nonempty string. |
| `status` | `model`, `clarify`, or `unsupported`. |
| `model` | Complete model object below for `model`; JSON `null` otherwise. |
| `questions` | For `clarify`, nonempty array of objects with exactly `field` and `question`, both nonempty strings. Otherwise `[]`. |
| `reason` | String; nonempty for `clarify` or `unsupported`. Explain ambiguity or capability gap. |

Use `clarify` when a required rule or parameter is missing and materially affects
behavior. `field` identifies the exact missing model field, e.g.
`missions/<id>/delay_hours`. Do not silently invent it. Use `unsupported` when the
requested semantics cannot be expressed by this profile. A `model` must fully
express the requested rules within the supported semantics; no pseudocode.

## General constraints

Every object below has **exactly** its listed fields; optional values must still
be present as `null` or an empty list/dictionary when applicable. All `id` values
are nonempty stable strings, unique within their table. Use the task's IDs when
supplied. References name IDs in the prescribed table. Unknown operations,
fields, units, references, and cyclic mission dependencies reject.

All time fields end with `_hours`, accept finite nonnegative numbers, and denote
hours. They are rounded once to integer microseconds. Horizon, report interval,
mission duration, and PM interval/duration must be positive and remain at least
one microsecond after rounding. Horizon must contain a whole number of report
intervals, with at most 10,000 intervals. Each entity table and each process's
step list contains at most 1,000 rows. The runtime executes at most 100,000
calendar events. Boolean values are not numeric inputs. Never use NaN/Infinity.

## Complete model fields

| Field | Type and constraint |
|---|---|
| `horizon_hours` | Positive hours; events at the horizon are included. |
| `report_interval_hours` | Positive hours; observation only. |
| `rng_profile` | `none` or `external-events/v1`; native random generation is unsupported. |
| `aircraft` | Nonempty array of aircraft rows. |
| `resources` | Array of reusable capacity-resource rows; can be empty. |
| `processes` | Array of preparation-process rows; each mission must reference one. |
| `missions` | Nonempty array of mission rows. |
| `nodes` | Array of physical-stock-node rows; can be empty. |
| `routes` | Array of directed transport rows; can be empty. |
| `external_events` | Array of explicit driver rows; can be empty. |

Aircraft row (all fields required):

| Field | Type and meaning |
|---|---|
| `id`, `type` | Nonempty strings; mission requirements reference `type`. |
| `turnround_hours` | Nonnegative delay after a successful return, when no flight-PM begins. |
| `repair_mode` | `none`, `direct`, or `replacement`. |
| `repair_hours` | Direct repair duration. |
| `remove_hours`, `fit_hours`, `item_repair_hours` | Replacement repair durations; supply zero when irrelevant. |
| `stock_node`, `repair_node` | Node IDs or `null`; both required for replacement. |
| `installed_item` | Unique nonempty physical item ID for replacement; `null` otherwise. |
| `pm` | `null` or exactly `{ "id": string, "clock": "calendar"|"flight", "interval_hours": positive number, "duration_hours": positive number }`. |

`resources` row: exactly `{ "id": string, "capacity": nonnegative integer }`.
Resource capacity applies to preparation steps. Direct repair and PM do not
accept resource demands; do not claim repair-crew competition is supported.

`processes` row: exactly `{ "id": string, "scalar_hours": nonnegative number,
"steps": array }`. A step has exactly `{ "id": string, "duration_hours":
nonnegative number, "demands": { resource_id: positive integer, ... } }`.
Step IDs are unique inside a process. Steps execute serially in list order for
each aircraft. A nonempty list **replaces** scalar duration for actual work;
`scalar_hours` still determines the early feasibility cutoff. An empty step list
means one scalar-duration step without resources. `demands` may be `{}`.

`missions` row:

| Field | Type and meaning |
|---|---|
| `id` | Stable string. |
| `start_hours` | Scheduled earliest launch; strictly before horizon after rounding. |
| `notice_hours` | Allocation/preparation notice; `0 <= notice <= start`. |
| `duration_hours` | Positive flight duration measured from actual launch. |
| `delay_hours` | Nonnegative launch tolerance; latest launch = start + delay. |
| `priority` | Nonnegative integer; smaller is dispatched first. Equal priorities preserve row order. |
| `requirements` | Nonempty `{ aircraft_type: positive integer, ... }`. |
| `process` | Existing process ID; applied separately to each allocated aircraft. |
| `depends_on` | List of existing mission IDs; each must have returned successfully before launch. Cycles reject. |

Aircraft selection follows aircraft row order among eligible matching types.
Turnround aircraft may be preassigned but cannot prepare until ready. All
formation members must be prepared before launch. Mission dependencies guard
launch, not allocation or preparation.

`nodes` row: exactly `{ "id": string, "items": [string, ...] }`. Each physical
item identity is unique globally across initial stock, installed aircraft items,
and future `in_transfer` additions.

`routes` row: exactly `{ "id": string, "source": node_id, "destination":
node_id, "duration_hours": nonnegative number }`. No self/duplicate directed
route. Replacement with distinct stock/repair nodes requires routes in both
directions. There is no automatic reorder policy.

`external_events` row always has exactly `id`, `time_hours`, `operation`,
`aircraft`, `node`, `item`, `value_hours`. Time is within the horizon inclusive.

| Operation | Required values and execution preconditions |
|---|---|
| `fault` | `aircraft` ID with direct/replacement repair; `node:null`, `item:null`, `value_hours:0`. Requires `external-events/v1` and a healthy flying aircraft at the event. Marks mission aborted; scheduled return remains. |
| `damaged_arrival` | Direct-repair aircraft; other values as fault. Requires `external-events/v1`, healthy flying aircraft in a single-aircraft mission. Ends flight immediately and starts repair. |
| `in_transfer` | `aircraft:null`, existing `node`, new `item` ID, `value_hours:0`. Adds one physical item to nominal/on-hand stock. |
| `set_repair_duration` | Direct-repair aircraft, `node:null`, `item:null`, nonnegative `value_hours`. Changes future repair duration; rejects while repair is in progress. |

## Timing and capability boundaries

Events order by tick, phase, insertion sequence. At the same time: completions
and arrivals, fault/PM drivers, notices, dispatch, early feasibility cutoff,
then final cutoff. Same-time zero-duration work converges before observations.
A completion at latest launch can therefore release resources and permit launch.

At `max(notice, start + delay - scalar)`, incomplete aircraft allocation or
permanently insufficient resource capacity cancels the mission. Temporary
occupancy alone does not. At `start + delay`, a still-waiting mission cancels.
Cancellation releases its owned resources and aircraft, invalidates unfinished
work completion tokens, and wakes dispatch. There is no arbitrary user-defined
cancel event or preemptive scheduling rule.

Calendar PM first becomes due at its interval, waits for a free landed asset,
and resets its calendar interval after completion. Flight PM accumulates only
flight exposure, checks on return (including aborted flights), and resets at PM
completion. A pending PM obligation survives repair; repair completes before
pending PM starts. No in-flight PM interruption is modeled. Each aircraft has
at most one PM clock. Native stochastic faults/distributions, multiple PM clocks
per aircraft, custom priorities for repair, and arbitrary expression/code
execution are outside this profile. Report samples do not alter scheduling.

## Minimal unrelated valid example

This synthetic example is documentation, not a task answer. It uses one aircraft,
no capacity resources, no failure, and no maintenance.

```json
{
  "task_id": "documentation-example",
  "status": "model",
  "model": {
    "horizon_hours": 6,
    "report_interval_hours": 0.5,
    "rng_profile": "none",
    "aircraft": [{
      "id": "DEMO-A", "type": "demo-type", "turnround_hours": 0,
      "repair_mode": "none", "repair_hours": 0, "remove_hours": 0,
      "fit_hours": 0, "item_repair_hours": 0, "stock_node": null,
      "repair_node": null, "installed_item": null, "pm": null
    }],
    "resources": [],
    "processes": [{"id": "DEMO-P", "scalar_hours": 0.25, "steps": []}],
    "missions": [{
      "id": "DEMO-M", "start_hours": 1.25, "notice_hours": 0.5,
      "duration_hours": 0.75, "delay_hours": 0.5, "priority": 0,
      "requirements": {"demo-type": 1}, "process": "DEMO-P", "depends_on": []
    }],
    "nodes": [], "routes": [], "external_events": []
  },
  "questions": [],
  "reason": "Complete deterministic documentation example."
}
```


修复实验由控制器执行反馈工具。参与者只读取分配条件的feedback.json，不得自行调用运行器或浏览internal/private目录。
