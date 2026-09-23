"""Independent, deliberately scanning interpreter for the experimental Plan.

This module shares only the serialized contract with engine.py. It uses named
mutable records, a linear minimum over pending events, and a global waiter scan.
It is not the legacy spare_mvp semantic reference.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any


def _duration(seed: int, identity: str, generation: int, lower: int, upper: int) -> int:
    value = 2166136261
    for byte in (str(seed) + "|" + identity + "|" + str(generation)).encode("utf-8"):
        value = ((value ^ byte) * 16777619) & 0xFFFFFFFF
    value = (value ^ (value << 13)) & 0xFFFFFFFF
    value = (value ^ (value >> 17)) & 0xFFFFFFFF
    value = (value ^ (value << 5)) & 0xFFFFFFFF
    return lower + value % (upper - lower + 1)


def run_plan(plan: Any, seed: int = 0, trace: bool = True) -> dict[str, Any]:
    """Execute using named state and exhaustive scans, without optimized code."""
    if type(seed) is not int or not 0 <= seed <= 0xFFFFFFFF:
        raise ValueError("seed must be an integer in [0, 2^32-1]")
    data = deepcopy(plan.to_dict() if hasattr(plan, "to_dict") else plan)
    if data.get("schema") != "plan/v1" or data.get("profile") != "ir-native-event-v1":
        raise ValueError("unsupported reference plan/profile")
    asset_names = [item["id"] for item in data["assets"]]
    resource_names = [item["id"] for item in data["resources"]]
    process_names = [item["id"] for item in data["processes"]]
    assets = {
        item["id"]: {"state": item["initial_state"], "owner": None}
        for item in data["assets"]
    }
    resources = {
        item["id"]: {"amount": item["initial"], "kind": item["kind"]}
        for item in data["resources"]
    }
    processes: dict[str, dict[str, Any]] = {}
    for spec in data["processes"]:
        processes[spec["id"]] = {
            "status": 0,
            "chosen": None,
            "started": -1,
            "finished": -1,
            "sampled": -1,
            "generation": 0,
            "completed": 0,
            "candidates": [asset_names[index] for index in spec["candidates"]],
            "needs": {resource_names[index]: qty for index, qty in spec["needs"]},
            "after": [process_names[index] for index in spec["after"]],
            "required_state": spec["required_state"],
            "finish_state": spec["finish_state"],
            "duration": spec["duration"],
            "release": spec["release"],
            "interruptible": spec["interruptible"],
            "repeat_delay": spec.get("repeat_delay"),
        }
    events: list[tuple[int, int, str, Any]] = []
    pending_requests: set[str] = set()
    event_sequence = 0
    now = 0
    history: list[list[Any]] = []
    counters = {"events": 0, "waiter_visits": 0, "attempts": 0, "event_list_visits": 0}

    def emit(kind: str, identity: str, asset: str | None, value: int) -> None:
        if trace:
            history.append([now, kind, identity, asset or "", value])

    def schedule(time: int, kind: str, payload: Any) -> None:
        nonlocal event_sequence
        events.append((time, event_sequence, kind, payload))
        event_sequence += 1

    def request(identity: str) -> None:
        if identity not in pending_requests and processes[identity]["status"] == 1:
            pending_requests.add(identity)
            schedule(now, "request", identity)

    def notify(changed_assets: set[str], changed_resources: set[str], completed: str | None = None) -> None:
        # Visit all process records, including unrelated and historic records.
        # The notification predicate preserves the specified targeted FIFO rule.
        for identity in process_names:
            counters["waiter_visits"] += 1
            record = processes[identity]
            if record["status"] != 1:
                continue
            affected = any(name in changed_assets for name in record["candidates"])
            affected = affected or any(name in changed_resources for name in record["needs"])
            affected = affected or (completed is not None and completed in record["after"])
            if affected:
                request(identity)

    def release(identity: str) -> tuple[set[str], set[str]]:
        record = processes[identity]
        changed_resources: set[str] = set()
        for name, quantity in record["needs"].items():
            if resources[name]["kind"] == "capacity":
                resources[name]["amount"] += quantity
                changed_resources.add(name)
        chosen = record["chosen"]
        if chosen is not None:
            assets[chosen]["owner"] = None
        return ({chosen} if chosen is not None else set(), changed_resources)

    for identity in process_names:
        start = processes[identity]["release"]
        if start is not None:
            schedule(start, "activate", identity)
    for event in data["events"]:
        schedule(event["time"], "external", event)

    while events:
        counters["event_list_visits"] += len(events)
        position = min(range(len(events)), key=lambda index: events[index][:2])
        time, _, kind, payload = events.pop(position)
        if time > data["horizon"]:
            break
        now = time
        counters["events"] += 1
        if counters["events"] > 10_000_000:
            raise RuntimeError("experimental reference event budget exceeded")
        if kind in ("activate", "request"):
            identity = payload
            record = processes[identity]
            if kind == "request":
                pending_requests.discard(identity)
                if record["status"] != 1:
                    continue
            else:
                if record["status"] in (1, 2):
                    continue
                if record["status"] in (3, 4):
                    record["generation"] += 1
                    record["chosen"] = None
                    record["started"] = -1
                    record["finished"] = -1
                    record["sampled"] = -1
                record["status"] = 1
            counters["attempts"] += 1
            if any(processes[name]["completed"] == 0 for name in record["after"]):
                continue
            chosen = next(
                (name for name in record["candidates"]
                 if assets[name]["state"] == record["required_state"] and assets[name]["owner"] is None),
                None,
            )
            if record["candidates"] and chosen is None:
                continue
            if any(resources[name]["amount"] < quantity for name, quantity in record["needs"].items()):
                continue
            record["chosen"] = chosen
            record["status"] = 2
            record["started"] = now
            if chosen is not None:
                assets[chosen]["owner"] = identity
            for name, quantity in record["needs"].items():
                resources[name]["amount"] -= quantity
            lower, upper = record["duration"]
            duration = lower if lower == upper else _duration(seed, identity, record["generation"], lower, upper)
            record["sampled"] = duration
            if lower != upper:
                emit("random", identity, chosen, duration)
            emit("start", identity, chosen, duration)
            schedule(now + duration, "complete", (identity, record["generation"]))
        elif kind == "complete":
            identity, generation = payload
            record = processes[identity]
            if record["status"] != 2 or record["generation"] != generation:
                continue
            record["status"] = 3
            record["finished"] = now
            record["completed"] += 1
            changed_assets, changed_resources = release(identity)
            chosen = record["chosen"]
            if chosen is not None:
                assets[chosen]["state"] = record["finish_state"]
            emit("complete", identity, chosen, 0)
            if record["repeat_delay"] is not None:
                schedule(now + record["repeat_delay"], "activate", identity)
            notify(changed_assets, changed_resources, identity)
        else:
            event = payload
            if event.get("repeat_every") is not None:
                schedule(now + event["repeat_every"], "external", event)
            if event["op"] == "set_state":
                asset_name = asset_names[event["target"]]
                asset = assets[asset_name]
                if asset["state"] == event["value"]:
                    continue
                changed_resources: set[str] = set()
                owner = asset["owner"]
                if owner is not None:
                    record = processes[owner]
                    if not record["interruptible"]:
                        raise RuntimeError("state change would interrupt a noninterruptible process")
                    record["status"] = 4
                    _, changed_resources = release(owner)
                    emit("abort", owner, asset_name, 0)
                asset["state"] = event["value"]
                emit("state", event["id"], asset_name, event["value"])
                if event["trigger"] is not None:
                    schedule(now, "activate", process_names[event["trigger"]])
                notify({asset_name}, changed_resources)
            elif event["op"] == "add_stock":
                resource_name = resource_names[event["target"]]
                resources[resource_name]["amount"] += event["value"]
                if resources[resource_name]["amount"] > (1 << 63) - 1:
                    raise RuntimeError("stock overflow")
                emit("stock", event["id"], None, resources[resource_name]["amount"])
                notify(set(), {resource_name})
            else:
                raise ValueError(f"unsupported operation {event['op']!r}")

    return {
        "profile": data["profile"],
        "fingerprint": data["fingerprint"],
        "seed": seed,
        "assets": [assets[name]["state"] for name in asset_names],
        "owners": [process_names.index(assets[name]["owner"]) if assets[name]["owner"] is not None else -1 for name in asset_names],
        "resources": [resources[name]["amount"] for name in resource_names],
        "status": [processes[name]["status"] for name in process_names],
        "selected": [asset_names.index(processes[name]["chosen"]) if processes[name]["chosen"] is not None else -1 for name in process_names],
        "started": [processes[name]["started"] for name in process_names],
        "finished": [processes[name]["finished"] for name in process_names],
        "sampled": [processes[name]["sampled"] for name in process_names],
        "generation": [processes[name]["generation"] for name in process_names],
        "completed": [processes[name]["completed"] for name in process_names],
        "trace": history,
        "diagnostics": counters,
    }


run = run_plan
