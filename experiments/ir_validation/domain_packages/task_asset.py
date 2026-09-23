"""Reusable task/asset domain grammar; concrete packages own their vocabularies.

This module is a domain implementation helper, not part of the generic
compiler. Other adapters can implement different Business schemas directly.
"""
from __future__ import annotations

from dataclasses import dataclass
import json
from validation import (PROFILE, RULES, _dag, _duration, _fail, _fingerprint,
                        _identity, _integer, _keys, _list, _needs, _unique)

def validate_task_asset(raw: dict, *, domain: str, asset_key: str, job_key: str, outage_key: str) -> dict:
    """Validate the narrow, explicit domain schema; return an independent copy."""
    _keys(raw, {"schema", "profile", "domain", "model_id", "revision", "time_unit", "horizon", "rules", "resources", "arrivals", asset_key, job_key, outage_key}, "business")
    if raw.get("schema") != "business/v1" or raw.get("profile") != PROFILE:
        _fail("unsupported Business IR schema/profile")
    if raw.get("time_unit") != "tick":
        _fail("unsupported time unit (expected tick)")
    if raw.get("domain") != domain:
        _fail("Business IR domain does not match selected adapter")
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


def lower_task_asset(business: dict, *, asset_key: str, job_key: str, outage_key: str) -> dict:
    """Domain packages lower into one set of domain-free process/event semantics."""
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
class TaskAssetDomain:
    domain: str
    asset_key: str
    job_key: str
    outage_key: str

    def validate_business(self, raw: dict) -> dict:
        return validate_task_asset(raw, domain=self.domain, asset_key=self.asset_key,
                                   job_key=self.job_key, outage_key=self.outage_key)

    def lower_core(self, business: dict) -> dict:
        return lower_task_asset(business, asset_key=self.asset_key,
                                job_key=self.job_key, outage_key=self.outage_key)
