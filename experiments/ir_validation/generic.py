"""Small, explicit IR-native compiler and generic indexed event executor.

No legacy aircraft semantics are implied. See SPEC.md for this profile.
Only compile_business/lower_core contain domain adapters; the execution plan
and executor have no aircraft/production branches.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
from heapq import heappop, heappush
import json
from typing import Any


PROFILE = "ir-native-event-v1"
RULES = {"selection": "first_available", "acquisition": "atomic", "stock_abort": "consume"}
MAX_INTEGER = (1 << 63) - 1


class ValidationError(ValueError):
    pass


def _fail(message: str) -> None:
    raise ValidationError(message)


def _keys(value: Any, allowed: set[str], where: str) -> None:
    if not isinstance(value, dict):
        _fail(f"{where}: expected object")
    unknown = set(value) - allowed
    if unknown:
        _fail(f"{where}: unsupported fields {sorted(unknown)}")


def _integer(value: Any, where: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum or value > MAX_INTEGER:
        _fail(f"{where}: expected integer in [{minimum},{MAX_INTEGER}]")
    return value


def _identity(value: Any, where: str) -> str:
    if not isinstance(value, str) or not value or "|" in value:
        _fail(f"{where}: expected nonempty stable ID without '|'")
    return value


def _list(value: Any, where: str) -> list:
    if not isinstance(value, list):
        _fail(f"{where}: expected list")
    return value


def _fingerprint(value: Any) -> str:
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()


def _duration(value: Any, where: str) -> list[int]:
    if not isinstance(value, list) or len(value) != 2:
        _fail(f"{where}: duration must be [lo,hi] integer ticks")
    lo, hi = (_integer(v, where) for v in value)
    if lo > hi:
        _fail(f"{where}: duration lo exceeds hi")
    return [lo, hi]


def _unique(rows: list[dict], where: str) -> dict[str, dict]:
    found = {}
    for i, row in enumerate(rows):
        if not isinstance(row, dict):
            _fail(f"{where}/{i}: expected object")
        ident = _identity(row.get("id"), f"{where}/{i}/id")
        if ident in found:
            _fail(f"{where}: duplicate id {ident}")
        found[ident] = row
    return found


def _needs(raw: Any, resources: dict, where: str) -> dict:
    if not isinstance(raw, dict):
        _fail(f"{where}: needs must be object")
    result = {}
    for resource, quantity in raw.items():
        if resource not in resources:
            _fail(f"{where}: unknown resource {resource}")
        result[resource] = _integer(quantity, where, 1)
        if resources[resource]["kind"] == "capacity" and quantity > resources[resource]["initial"]:
            _fail(f"{where}: impossible capacity request {resource}")
    return result


def _dag(after: list[list[int]]) -> None:
    indegree = [len(a) for a in after]
    following = [[] for _ in after]
    for child, parents in enumerate(after):
        for parent in parents:
            following[parent].append(child)
    todo = [i for i, value in enumerate(indegree) if value == 0]
    count = 0
    while todo:
        node = todo.pop()
        count += 1
        for child in following[node]:
            indegree[child] -= 1
            if indegree[child] == 0:
                todo.append(child)
    if count != len(after):
        _fail("process predecessor graph contains a cycle")


def compile_business(raw: dict) -> dict:
    """Validate the narrow, explicit domain schema; return an independent copy."""
    _keys(raw, {"schema", "profile", "domain", "model_id", "revision", "time_unit", "horizon", "rules", "fleet", "missions", "maintenance", "machines", "jobs", "outages", "resources", "arrivals"}, "business")
    if raw.get("schema") != "business/v1" or raw.get("profile") != PROFILE:
        _fail("unsupported Business IR schema/profile")
    if raw.get("time_unit") != "tick":
        _fail("unsupported time unit (expected tick)")
    domain = raw.get("domain")
    if domain not in ("aircraft", "production"):
        _fail("unsupported domain")
    asset_key, job_key, outage_key = ("fleet", "missions", "maintenance") if domain == "aircraft" else ("machines", "jobs", "outages")
    alien = {"fleet", "missions", "maintenance", "machines", "jobs", "outages"} - {asset_key, job_key, outage_key}
    if any(key in raw for key in alien):
        _fail("domain contains tables owned by another domain")
    business = json.loads(json.dumps(raw))
    _identity(business.get("model_id"), "model_id")
    _identity(business.get("revision"), "revision")
    _integer(business.get("horizon"), "horizon")
    _keys(business.get("rules", {}), set(RULES), "rules")
    for name, value in business.get("rules", {}).items():
        if value != RULES[name]:
            _fail(f"unsupported rule {name}={value}")
    business["rules"] = dict(RULES)
    for key in (asset_key, job_key, outage_key, "resources", "arrivals"):
        business[key] = _list(business.get(key, []), key)
    for asset in business[asset_key]:
        _keys(asset, {"id", "initial_state"}, asset_key)
        state = _integer(asset.get("initial_state", 0), "asset state")
        if state not in (0, 1):
            _fail("asset state must be 0 or 1")
        asset["initial_state"] = state
    assets = _unique(business[asset_key], asset_key)
    for resource in business["resources"]:
        _keys(resource, {"id", "kind", "initial"}, "resource")
        if resource.get("kind") not in ("capacity", "stock"):
            _fail("unknown resource kind")
        _integer(resource.get("initial"), "resource initial")
    resources = _unique(business["resources"], "resources")
    jobs = _unique(business[job_key], job_key)
    for job in business[job_key]:
        _keys(job, {"id", "release", "duration", "eligible", "needs", "after", "repeat_delay"}, job_key)
        job["release"] = job.get("release", 0)
        if job["release"] is not None:
            _integer(job["release"], "release")
        job["duration"] = _duration(job.get("duration"), "duration")
        job["eligible"] = _list(job.get("eligible", []), "eligible")
        if len(set(job["eligible"])) != len(job["eligible"]):
            _fail("duplicate candidate reference")
        if any(asset not in assets for asset in job["eligible"]):
            _fail("unknown candidate asset")
        job["needs"] = _needs(job.get("needs", {}), resources, job["id"])
        job["after"] = _list(job.get("after", []), "after")
        if len(set(job["after"])) != len(job["after"]) or any(parent not in jobs for parent in job["after"]):
            _fail("unknown/duplicate process predecessor")
        job["repeat_delay"] = job.get("repeat_delay")
        if job["repeat_delay"] is not None:
            _integer(job["repeat_delay"], "repeat_delay", 1)
    job_indices = {name: i for i, name in enumerate(jobs)}
    _dag([[job_indices[parent] for parent in row["after"]] for row in business[job_key]])
    outages = _unique(business[outage_key], outage_key)
    for outage in business[outage_key]:
        _keys(outage, {"id", "asset", "at", "duration", "needs", "repeat_every"}, outage_key)
        if outage.get("asset") not in assets:
            _fail("outage refers to unknown asset")
        if "restore:" + outage["id"] in jobs:
            _fail("generated restoration process id collides with job id")
        _integer(outage.get("at"), "outage at")
        outage["duration"] = _duration(outage.get("duration"), "outage duration")
        outage["needs"] = _needs(outage.get("needs", {}), resources, outage["id"])
        outage["repeat_every"] = outage.get("repeat_every")
        if outage["repeat_every"] is not None:
            _integer(outage["repeat_every"], "repeat_every", 1)
    arrivals = _unique(business["arrivals"], "arrivals")
    if set(arrivals) & set(outages):
        _fail("duplicate explicit event ID across arrival/outage tables")
    for arrival in business["arrivals"]:
        _keys(arrival, {"id", "time", "resource", "quantity"}, "arrival")
        _integer(arrival.get("time"), "arrival time")
        _integer(arrival.get("quantity"), "arrival quantity", 1)
        if arrival.get("resource") not in resources or resources[arrival["resource"]]["kind"] != "stock":
            _fail("arrival must reference stock resource")
    return business


def lower_core(business: dict) -> dict:
    """Domain packages lower into one set of domain-free process/event semantics."""
    business = compile_business(business)
    aircraft = business["domain"] == "aircraft"
    asset_key, job_key, outage_key = ("fleet", "missions", "maintenance") if aircraft else ("machines", "jobs", "outages")
    core = {"schema": "core/v1", "profile": PROFILE, "time_unit": "tick", "model_id": business["model_id"], "revision": business["revision"], "horizon": business["horizon"], "business_fingerprint": _fingerprint(business), "assets": business[asset_key], "resources": business["resources"], "processes": [], "events": [], "source_map": {}}
    for index, asset in enumerate(core["assets"]):
        core["source_map"]["asset:" + asset["id"]] = f"/{asset_key}/{index}"
    for index, resource in enumerate(core["resources"]):
        core["source_map"]["resource:" + resource["id"]] = f"/resources/{index}"
    for index, job in enumerate(business[job_key]):
        core["processes"].append({"id": job["id"], "candidates": job["eligible"], "required_state": 0, "finish_state": 0, "needs": job["needs"], "duration": job["duration"], "after": job["after"], "release": job["release"], "interruptible": True, "repeat_delay": job["repeat_delay"]})
        core["source_map"]["process:" + job["id"]] = f"/{job_key}/{index}"
    for index, outage in enumerate(business[outage_key]):
        pid = "restore:" + outage["id"]
        core["processes"].append({"id": pid, "candidates": [outage["asset"]], "required_state": 1, "finish_state": 0, "needs": outage["needs"], "duration": outage["duration"], "after": [], "release": None, "interruptible": False, "repeat_delay": None})
        core["events"].append({"id": outage["id"], "time": outage["at"], "op": "set_state", "target": outage["asset"], "value": 1, "trigger": pid, "repeat_every": outage["repeat_every"]})
        core["source_map"]["process:" + pid] = f"/{outage_key}/{index}"
        core["source_map"]["event:" + outage["id"]] = f"/{outage_key}/{index}"
    for index, arrival in enumerate(business["arrivals"]):
        core["events"].append({"id": arrival["id"], "time": arrival["time"], "op": "add_stock", "target": arrival["resource"], "value": arrival["quantity"], "trigger": None, "repeat_every": None})
        core["source_map"]["event:" + arrival["id"]] = f"/arrivals/{index}"
    return core


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
        processes.append(Process(process["id"], tuple(ai[x] for x in candidates), process["required_state"], process["finish_state"], tuple((ri[x], q) for x, q in needs.items()), tuple(_duration(process.get("duration"), "duration")), tuple(pi[x] for x in after), release, process["interruptible"], repeat))
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


def build_plan(raw: dict) -> Plan:
    return compile_plan(lower_core(compile_business(raw)))


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
