"""Small, explicit IR-native compiler and generic indexed event executor.

No legacy aircraft semantics are implied. See SPEC.md for this profile.
Business adapters are injected from domain packages. The compiler, execution
plan and executor contain no concrete domain mappings or branches.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from heapq import heappop, heappush
import json
from typing import Any


from validation import (PROFILE, MAX_INTEGER, ValidationError, _dag, _duration,
                        _fail, _fingerprint, _identity, _integer, _keys, _list,
                        _needs, _unique)
from domain_packages import DomainRegistry, builtin_registry


def compile_business(raw: dict, *, registry: DomainRegistry | None = None) -> dict:
    """Resolve an injected domain adapter; it owns Business schema validation."""
    if not isinstance(raw, dict):
        _fail("business: expected object")
    if raw.get("schema") != "business/v1" or raw.get("profile") != PROFILE:
        _fail("unsupported Business IR schema/profile")
    if raw.get("time_unit") != "tick":
        _fail("unsupported time unit (expected tick)")
    _identity(raw.get("model_id"), "model_id")
    _identity(raw.get("revision"), "revision")
    _integer(raw.get("horizon"), "horizon")
    selected = builtin_registry() if registry is None else registry
    return selected.resolve(raw.get("domain")).validate_business(raw)


def lower_core(business: dict, *, registry: DomainRegistry | None = None) -> dict:
    """Dispatch through the same adapter registry; no domain vocabulary here."""
    selected = builtin_registry() if registry is None else registry
    validated = compile_business(business, registry=selected)
    return selected.resolve(validated.get("domain")).lower_core(validated)


@dataclass(frozen=True)
class Asset:
    id: str
    initial_state: int


@dataclass(frozen=True)
class Resource:
    id: str
    kind: str
    initial: int


@dataclass(frozen=True)
class Process:
    id: str
    candidates: tuple[int, ...]
    required_state: int
    finish_state: int
    needs: tuple[tuple[int, int], ...]
    duration: tuple[int, int]
    after: tuple[int, ...]
    release: int | None
    interruptible: bool
    repeat_delay: int | None


@dataclass(frozen=True)
class Event:
    id: str
    time: int
    op: str
    target: int
    value: int
    trigger: int | None
    repeat_every: int | None


@dataclass(frozen=True)
class Plan:
    model_id: str
    revision: str
    horizon: int
    business_fingerprint: str
    core_fingerprint: str
    fingerprint: str
    assets: tuple[Asset, ...]
    resources: tuple[Resource, ...]
    processes: tuple[Process, ...]
    events: tuple[Event, ...]
    successors: tuple[tuple[int, ...], ...]
    source_map: tuple[tuple[str, str], ...]
    schema: str = "plan/v1"
    profile: str = PROFILE
    time_unit: str = "tick"

    def to_dict(self) -> dict:
        value = asdict(self)
        value["source_map"] = dict(self.source_map)
        return json.loads(json.dumps(value))


def compile_plan(core: dict) -> Plan:
    """Resolve names, validate operators/dependencies, and freeze dense tables."""
    _keys(core, {"schema", "profile", "time_unit", "model_id", "revision", "horizon", "business_fingerprint", "assets", "resources", "processes", "events", "source_map"}, "core")
    if core.get("schema") != "core/v1" or core.get("profile") != PROFILE or core.get("time_unit") != "tick":
        _fail("unsupported Core IR schema/profile/unit")
    _identity(core.get("model_id"), "model_id")
    _identity(core.get("revision"), "revision")
    _integer(core.get("horizon"), "horizon")
    assets_raw = _list(core.get("assets"), "core assets")
    resources_raw = _list(core.get("resources"), "core resources")
    processes_raw = _list(core.get("processes"), "core processes")
    events_raw = _list(core.get("events"), "core events")
    asset_names = _unique(assets_raw, "core assets")
    resource_names = _unique(resources_raw, "core resources")
    process_names = _unique(processes_raw, "core processes")
    _unique(events_raw, "core events")
    ai = {name: i for i, name in enumerate(asset_names)}
    ri = {name: i for i, name in enumerate(resource_names)}
    pi = {name: i for i, name in enumerate(process_names)}
    assets, resources, processes, events = [], [], [], []
    for asset in assets_raw:
        _keys(asset, {"id", "initial_state"}, "core asset")
        state = _integer(asset.get("initial_state"), "initial state")
        if state not in (0, 1):
            _fail("unknown initial state")
        assets.append(Asset(asset["id"], state))
    for resource in resources_raw:
        _keys(resource, {"id", "kind", "initial"}, "core resource")
        if resource.get("kind") not in ("capacity", "stock"):
            _fail("unknown resource kind")
        resources.append(Resource(resource["id"], resource["kind"], _integer(resource.get("initial"), "initial")))
    for process in processes_raw:
        _keys(process, {"id", "candidates", "required_state", "finish_state", "needs", "duration", "after", "release", "interruptible", "repeat_delay"}, "core process")
        candidates = _list(process.get("candidates"), "candidates")
        after = _list(process.get("after"), "after")
        if any(name not in ai for name in candidates) or len(set(candidates)) != len(candidates):
            _fail("unknown/duplicate candidate")
        if any(name not in pi for name in after) or len(set(after)) != len(after):
            _fail("unknown/duplicate predecessor")
        needs = _needs(process.get("needs"), resource_names, "core process")
        for state in ("required_state", "finish_state"):
            if type(process.get(state)) is not int or process[state] not in (0, 1):
                _fail("unknown process state")
        release, repeat = process.get("release"), process.get("repeat_delay")
        if release is not None:
            _integer(release, "release")
        if repeat is not None:
            _integer(repeat, "repeat_delay", 1)
        if type(process.get("interruptible")) is not bool:
            _fail("interruptible must be boolean")
        processes.append(Process(process["id"], tuple(ai[x] for x in candidates), process["required_state"], process["finish_state"], tuple(sorted((ri[x], q) for x, q in needs.items())), tuple(_duration(process.get("duration"), "duration")), tuple(pi[x] for x in after), release, process["interruptible"], repeat))
    _dag([list(row.after) for row in processes])
    for event in events_raw:
        _keys(event, {"id", "time", "op", "target", "value", "trigger", "repeat_every"}, "core event")
        _integer(event.get("time"), "event time")
        trigger = event.get("trigger")
        if trigger is not None and trigger not in pi:
            _fail("unknown event trigger")
        repeat = event.get("repeat_every")
        if repeat is not None:
            _integer(repeat, "repeat_every", 1)
        if event.get("op") == "set_state":
            if event.get("target") not in ai or type(event.get("value")) is not int or event["value"] not in (0, 1):
                _fail("invalid set_state target/value")
            target = ai[event["target"]]
        elif event.get("op") == "add_stock":
            if event.get("target") not in ri or resource_names[event["target"]]["kind"] != "stock" or trigger is not None:
                _fail("invalid add_stock target/trigger")
            target = ri[event["target"]]
            _integer(event.get("value"), "stock increment", 1)
        else:
            _fail(f"unknown operation {event.get('op')}")
        events.append(Event(event["id"], event["time"], event["op"], target, event["value"], None if trigger is None else pi[trigger], repeat))
    successors = [[] for _ in processes]
    for child, process in enumerate(processes):
        for parent in process.after:
            successors[parent].append(child)
    source_map = core.get("source_map")
    if not isinstance(source_map, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in source_map.items()):
        _fail("source_map must map strings to source paths")
    if not isinstance(core.get("business_fingerprint"), str):
        _fail("missing business fingerprint")
    kwargs = dict(model_id=core["model_id"], revision=core["revision"], horizon=core["horizon"], business_fingerprint=core["business_fingerprint"], core_fingerprint=_fingerprint(core), assets=tuple(assets), resources=tuple(resources), processes=tuple(processes), events=tuple(events), successors=tuple(tuple(row) for row in successors), source_map=tuple(sorted(source_map.items())))
    provisional = Plan(fingerprint="", **kwargs)
    content = provisional.to_dict()
    del content["fingerprint"]
    return Plan(fingerprint=_fingerprint(content), **kwargs)


def build_plan(raw: dict, *, registry: DomainRegistry | None = None) -> Plan:
    selected = builtin_registry() if registry is None else registry
    return compile_plan(lower_core(compile_business(raw, registry=selected), registry=selected))


def sample_duration(seed: int, identity: str, generation: int, lo: int, hi: int) -> int:
    value = 2166136261
    for byte in f"{seed}|{identity}|{generation}".encode("utf-8"):
        value = ((value ^ byte) * 16777619) & 0xFFFFFFFF
    value = (value ^ (value << 13)) & 0xFFFFFFFF
    value = (value ^ (value >> 17)) & 0xFFFFFFFF
    value = (value ^ (value << 5)) & 0xFFFFFFFF
    return lo + value % (hi - lo + 1)


def _execute(plan: Plan, seed: int = 0, trace: bool = True, event_budget: int = 10_000_000):
    """Initialize private state, yield once, then execute the prepared state."""
    if not isinstance(plan, Plan) or plan.profile != PROFILE or plan.schema != "plan/v1" or plan.time_unit != "tick":
        _fail("run_plan requires compiled Plan with supported schema/profile/unit")
    _integer(plan.horizon, "plan horizon")
    if any(event.op not in ("set_state", "add_stock") for event in plan.events):
        _fail("unsupported compiled operation")
    _integer(seed, "seed")
    if seed > 0xFFFFFFFF:
        _fail("seed exceeds uint32")
    _integer(event_budget, "event budget", 1)
    count = len(plan.processes)
    states = [row.initial_state for row in plan.assets]
    owners = [-1] * len(plan.assets)
    quantities = [row.initial for row in plan.resources]
    status = [0] * count
    selected = [-1] * count
    started = [-1] * count
    finished = [-1] * count
    sampled = [-1] * count
    generation = [0] * count
    completed = [0] * count
    pending = [False] * count
    asset_waiters = [set() for _ in plan.assets]
    resource_waiters = [set() for _ in plan.resources]
    calendar = []
    history = []
    sequence = 0
    counters = {"events": 0, "attempts": 0, "waiter_inspections": 0, "candidate_checks": 0, "stale_completions": 0, "max_queue": 0}
    now = 0

    def enqueue(time: int, kind: int, index: int, gen: int = 0) -> None:
        nonlocal sequence
        if time <= plan.horizon:
            heappush(calendar, (time, sequence, kind, index, gen))
            sequence += 1
            counters["max_queue"] = max(counters["max_queue"], len(calendar))

    def record(kind: str, identity: str, asset: int = -1, value: int = 0) -> None:
        if trace:
            history.append([now, kind, identity, "" if asset < 0 else plan.assets[asset].id, value])

    def subscribe(index: int, add: bool) -> None:
        process = plan.processes[index]
        for asset in process.candidates:
            if add:
                asset_waiters[asset].add(index)
            else:
                asset_waiters[asset].discard(index)
        for resource, _ in process.needs:
            if add:
                resource_waiters[resource].add(index)
            else:
                resource_waiters[resource].discard(index)

    def notify(assets: list[int], resources: list[int], extra=()) -> None:
        affected = set(extra)
        for asset in assets:
            affected.update(asset_waiters[asset])
        for resource in resources:
            affected.update(resource_waiters[resource])
        counters["waiter_inspections"] += len(affected)
        for index in sorted(affected):
            if status[index] == 1 and not pending[index]:
                pending[index] = True
                enqueue(now, 1, index)

    def release(index: int) -> tuple[list[int], list[int]]:
        asset = selected[index]
        if asset >= 0:
            owners[asset] = -1
        resources = []
        for resource, quantity in plan.processes[index].needs:
            if plan.resources[resource].kind == "capacity":
                quantities[resource] += quantity
                resources.append(resource)
        return ([] if asset < 0 else [asset]), resources

    def attempt(index: int) -> None:
        process = plan.processes[index]
        counters["attempts"] += 1
        if any(completed[parent] == 0 for parent in process.after):
            subscribe(index, True)
            return
        asset = -1
        if process.candidates:
            for candidate in process.candidates:
                counters["candidate_checks"] += 1
                if states[candidate] == process.required_state and owners[candidate] < 0:
                    asset = candidate
                    break
            if asset < 0:
                subscribe(index, True)
                return
        if any(quantities[resource] < quantity for resource, quantity in process.needs):
            subscribe(index, True)
            return
        subscribe(index, False)
        status[index] = 2
        selected[index] = asset
        started[index] = now
        if asset >= 0:
            owners[asset] = index
        for resource, quantity in process.needs:
            quantities[resource] -= quantity
        lo, hi = process.duration
        duration = lo if lo == hi else sample_duration(seed, process.id, generation[index], lo, hi)
        sampled[index] = duration
        if lo != hi:
            record("random", process.id, asset, duration)
        record("start", process.id, asset, duration)
        enqueue(now + duration, 2, index, generation[index])

    # Runtime kinds: activation=0, retry=1, completion=2, explicit core event=3.
    for index, process in enumerate(plan.processes):
        if process.release is not None:
            enqueue(process.release, 0, index)
    for index, event in enumerate(plan.events):
        enqueue(event.time, 3, index)
    yield None  # Runtime.__init__ stops here: all sample initialization is done.
    while calendar:
        now, _, kind, index, gen = heappop(calendar)
        counters["events"] += 1
        if counters["events"] > event_budget:
            raise RuntimeError("event budget exceeded")
        if kind == 0:
            if status[index] in (1, 2):
                continue
            if status[index] in (3, 4):
                generation[index] += 1
                selected[index] = started[index] = finished[index] = sampled[index] = -1
            status[index] = 1
            attempt(index)
        elif kind == 1:
            pending[index] = False
            if status[index] == 1:
                attempt(index)
        elif kind == 2:
            if status[index] != 2 or generation[index] != gen:
                counters["stale_completions"] += 1
                continue
            process = plan.processes[index]
            changed_assets, changed_resources = release(index)
            asset = selected[index]
            if asset >= 0:
                states[asset] = process.finish_state
            status[index] = 3
            completed[index] += 1
            finished[index] = now
            record("complete", process.id, asset)
            if process.repeat_delay is not None:
                enqueue(now + process.repeat_delay, 0, index)
            notify(changed_assets, changed_resources, plan.successors[index])
        else:
            event = plan.events[index]
            if event.repeat_every is not None:
                enqueue(now + event.repeat_every, 3, index)
            if event.op == "add_stock":
                if quantities[event.target] > MAX_INTEGER - event.value:
                    raise RuntimeError("stock quantity exceeds int64 range")
                quantities[event.target] += event.value
                record("stock", event.id, value=quantities[event.target])
                notify([], [event.target])
            elif event.op == "set_state":
                asset = event.target
                if states[asset] == event.value:
                    continue
                changed_resources = []
                owner = owners[asset]
                if owner >= 0:
                    if not plan.processes[owner].interruptible:
                        raise RuntimeError("state change would interrupt a noninterruptible process")
                    _, changed_resources = release(owner)
                    status[owner] = 4
                    record("abort", plan.processes[owner].id, asset)
                states[asset] = event.value
                record("state", event.id, asset, event.value)
                if event.trigger is not None:
                    enqueue(now, 0, event.trigger)
                notify([asset], changed_resources)
            else:
                raise RuntimeError("unsupported compiled operation")
    counters.update(events_popped=counters["events"], request_attempts=counters["attempts"], waiter_visits=counters["waiter_inspections"])
    return {"profile": PROFILE, "fingerprint": plan.fingerprint, "seed": seed, "assets": states, "owners": owners, "resources": quantities, "status": status, "selected": selected, "started": started, "finished": finished, "sampled": sampled, "generation": generation, "completed": completed, "trace": history, "diagnostics": counters}


class Runtime:
    """One sample's private initialized state; run once after construction.

    Initialization includes arrays, waiter sets and the initial event heap.
    Execution begins at the first event pop. The generator only provides an
    explicit timing boundary; all scheduling is the generic heap above.
    """

    def __init__(self, plan: Plan, seed: int = 0, trace: bool = True, event_budget: int = 10_000_000):
        self._runner = _execute(plan, seed, trace, event_budget)
        next(self._runner)
        self._used = False

    def run(self) -> dict:
        if self._used:
            raise RuntimeError("sample Runtime already executed")
        self._used = True
        try:
            next(self._runner)
        except StopIteration as stop:
            return stop.value
        raise AssertionError("unexpected second initialization yield")


def run_plan(plan: Plan, seed: int = 0, trace: bool = True, event_budget: int = 10_000_000) -> dict:
    return Runtime(plan, seed, trace, event_budget).run()


def semantic_result(result: dict) -> dict:
    """Counters reflect implementation effort, not model semantics."""
    return {key: value for key, value in result.items() if key != "diagnostics"}
