"""Static native-table preparation and hand-ledger validation; never runs a model.

This is a narrow case-library writer, not a Project JSON interpreter, canonical
adapter, Plan compiler, or simulation runtime. Native behavior remains unknown.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parent
LIB = ROOT.parent
BASE = "861ce9e193046bc1c8cec276fdb85101044dbfaa"
CASES = ("B01", "B02", "C01", "C02", "C03")
spec = importlib.util.spec_from_file_location("a01_native_writer", LIB / "tools/generate_native.py")
writer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(writer)


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def encoded(value):
    return (json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def require(condition, message):
    if not condition:
        raise ValueError(message)


def integer(value, path, minimum=1):
    require(type(value) is int and value >= minimum, f"{path}: expected integer >= {minimum}")


def validate_parameters(p):
    require(set(p) == {"schema", "units", "site_id", "unit_id", "aircraft_type_id", "aircraft_ids",
                       "resources", "steps", "missions", "horizon_minutes", "result_interval_minutes"}, "unknown/missing parameter field")
    require(p["schema"] == "simlox-c03-common-parameters/v1", "unsupported parameter schema")
    require(p["units"] == {"time": "minute", "native_time": "hour", "resource": "count", "conversion": 60}, "invalid units or conversion")
    require(type(p["units"]["conversion"]) is int, "conversion type")
    ids = p["aircraft_ids"]
    require(len(ids) == 2 and len(set(ids)) == 2 and all(type(x) is str and x for x in ids), "two distinct aircraft identities required")
    for field in ("site_id", "unit_id", "aircraft_type_id"):
        require(type(p[field]) is str and p[field], f"invalid {field}")
    resources = p["resources"]
    require(len(resources) == 2, "exactly personnel and equipment pools required")
    require(all(set(r) == {"id", "kind", "capacity"} for r in resources), "resource fields")
    require([r["kind"] for r in resources] == ["personnel", "equipment"], "resource category order")
    require(len({r["id"] for r in resources}) == 2 and all(type(r["id"]) is str and r["id"] for r in resources), "duplicate/invalid resource identity")
    for r in resources:
        integer(r["capacity"], "resource capacity")
    require(resources[0]["capacity"] == 2 and resources[1]["capacity"] in (1, 2), "only equipment capacity 1 or 2 may vary; personnel fixed at 2")
    pool = {r["id"]: r["capacity"] for r in resources}
    require(len(p["steps"]) == 2, "two serial nonempty work steps required")
    require(len({s["id"] for s in p["steps"]}) == 2, "duplicate step identity")
    for s in p["steps"]:
        require(set(s) == {"id", "duration_minutes", "demands"}, "step fields")
        integer(s["duration_minutes"], "work duration")
        require(s["demands"], "empty resource demand cannot prove support work")
        for rid, quantity in s["demands"].items():
            require(rid in pool, f"unresolved resource reference: {rid}")
            integer(quantity, "resource demand")
            require(quantity <= pool[rid], "demand exceeds capacity")
    crew, device = (r["id"] for r in resources)
    require(p["steps"][0]["demands"] == {crew: 1} and p["steps"][1]["demands"] == {crew: 1, device: 1}, "unsupported step demand policy")
    require([s["duration_minutes"] for s in p["steps"]] == [10, 40], "frozen 10 + 40 minute serial work required")
    require(len(p["missions"]) == 2 and len({m["id"] for m in p["missions"]}) == 2, "two distinct missions required")
    for m in p["missions"]:
        require(set(m) == {"id", "aircraft_id", "notice_minutes", "planned_start_minutes", "delay_minutes", "flight_minutes"}, "mission fields")
        require(m["aircraft_id"] in ids, "unresolved aircraft reference")
        for key in ("notice_minutes", "planned_start_minutes", "delay_minutes", "flight_minutes"):
            integer(m[key], key)
        require(m["planned_start_minutes"] - m["notice_minutes"] == 60, "notice lead must be 60 minutes")
        require(m["delay_minutes"] == 30 and m["flight_minutes"] == 60, "frozen flight/deadline policy")
    require(len({m["aircraft_id"] for m in p["missions"]}) == 2, "aircraft double allocation")
    require([m["notice_minutes"] for m in p["missions"]] == [420, 440], "staggered request fixture required")
    integer(p["horizon_minutes"], "horizon")
    integer(p["result_interval_minutes"], "collection interval")
    require(p["horizon_minutes"] == 720 and p["result_interval_minutes"] == 30, "frozen observation range")


def build(case="C03", capacity=1, parameters=None, *, _check=True):
    require(case in CASES, "unsupported preparation case")
    integer(capacity, "capacity")
    require(capacity in (1, 2) and (case == "C03" or capacity == 2), "parents use nonbinding capacity 2")
    p = copy.deepcopy(parameters if parameters is not None else read(ROOT / "parameters.json"))
    # Caller parameters are validated before applying the only exposed variant.
    validate_parameters(p)
    p["resources"][1]["capacity"] = capacity
    a01 = read(LIB / "A01-single-aircraft-single-mission/parameters.json")
    model = writer.build(a01)  # reuses the existing SHA-pinned schema and writer
    set_rows = lambda name, rows: writer.set_rows(model, name, rows)
    for table in model["model"]["tables"]:
        for instance in table["instances"]:
            instance["rows"] = []
    sid, unit, site = (p[k] for k in ("aircraft_type_id", "unit_id", "site_id"))
    missions = p["missions"] if case == "C03" else p["missions"][:1]
    steps = p["steps"][:1] if case == "B01" else p["steps"]
    resources = [] if case in ("B01", "B02") else p["resources"][:1] if case == "C01" else p["resources"]
    resource_ids = {r["id"] for r in resources}
    set_rows("ProblemDescription", [{"PDESC": "Static resource contract candidate; native and GUI unverified"}])
    set_rows("ControlParameters", [{}]); set_rows("GlobalParameters", [{}])
    set_rows("Control", [{"NREPS": 1, "SIMPE": 12.0, "RSEED": "1", "APID": "AIR_BASIC", "RCINT": 0.5, "RCSTA": 0, "RCEND": 12.0, "ENPM": "N", "ENLOG": "Y"}])
    set_rows("System", [{"SID": sid, "DESCR": "Generic resource teaching aircraft", "FRT": 0, "OPID": "OPHOURS"}])
    set_rows("Station", [{"STID": site, "DESCR": "One teaching site", "QTY": 1, "TYPE": "WS"}])
    set_rows("Unit", [{"UNID": unit, "STID": site}])
    set_rows("SystemDeployment", [{"SID": sid, "USTID": unit, "QTYPS": len(missions), "UTIL": 1}])
    set_rows("MissionType", [{"MTID": m["id"], "NOS": 1, "MNOS": 1, "DURN": 1.0, "MSUCPT": 1, "TFOUT": .25, "TFRET": .25, "PRI": 1, "NOPER": 1.0} for m in missions])
    set_rows("OperationProfile", [{"PRID": "RESOURCE-SCHEDULE", "SPRID": m["id"], "STIM": m["planned_start_minutes"] / 60, "ITYPE": "SCHEDULED", "IQTY": 1, "IPER": 0, "DTIM": .5} for m in missions])
    set_rows("OperationParameter", [{}])
    set_rows("Operations", [{"USTID": unit, "PRID": "RESOURCE-SCHEDULE"}])
    set_rows("MissionPreparation", [{"MTID": m["id"], "SID": sid, "STID": site, "DURN": sum(s["duration_minutes"] for s in steps) / 60, "TID": "PREP"} for m in missions])
    set_rows("Tasks", [{"TID": "PREP", "DESCR": "Serial preparation candidate"}])
    set_rows("SubTaskType", [{"SUTID": s["id"], "DESCR": s["id"]} for s in steps])
    set_rows("TaskBreakDown", [{"TID": "PREP", "SEQ": i, "SUTID": s["id"], "DURN": s["duration_minutes"] / 60} for i, s in enumerate(steps, 1)])
    set_rows("Resource", [{"RID": r["id"], "DESCR": r["kind"], "TYPE": "SPECIAL"} for r in resources])
    set_rows("ResourceAllocation", [{"POINT": sid, "RID": r["id"], "STID": site, "RQTY": r["capacity"]} for r in resources])
    # Parent-level and subtask resource demands must not be silently duplicated.
    # SubTaskResource-only activation is an explicit pending native probe.
    set_rows("TaskResource", [])
    set_rows("SubTaskResource", [{"TID": "PREP", "SEQ": i, "RID": rid, "QTY": qty, "RPROB": 1} for i, s in enumerate(steps, 1) for rid, qty in s["demands"].items() if rid in resource_ids])
    kinds = ["MISSION", "SYSTEM"] + (["RESOURCE"] if resources else [])
    set_rows("ResultCollection", [{"RTYPE": kind, "RCINT": .5, "RCSTA": 0, "RCEND": 12.0} for kind in kinds])
    if _check:
        validate_native(model)
    return model


def validate_native(model):
    """Structural checks only: schema, types, key uniqueness and explicit refs."""
    schema = read(writer.SCHEMA)
    require(digest(writer.SCHEMA.read_bytes()) == writer.SCHEMA_SHA256, "schema fingerprint changed")
    require(set(model) == set(schema) and set(model["model"]) == set(schema["model"]), "native envelope changed")
    tables = model["model"]["tables"]
    require([t["name"] for t in tables] == [t["name"] for t in schema["model"]["tables"]], "native table membership/order changed")
    rows = {}
    for t, baseline in zip(tables, schema["model"]["tables"]):
        require(t["columns"] == baseline["columns"] and len(t["instances"]) == 1, "native column layout changed")
        require(t["instances"][0]["instance_name"] == "", "native instance name changed")
        keys = set(); records = []
        for row in t["instances"][0]["rows"]:
            require(len(row) == len(t["columns"]), "native row width")
            for value, column in zip(row, t["columns"]):
                if value is None:
                    # A01/A02's accepted native input contains this single
                    # all-null built-in operation-parameter placeholder.
                    require(not column.get("key") or (t["name"] == "OperationParameter" and all(v is None for v in row)), "null native key")
                    continue
                kind = column["datatype"]
                require((kind == "string" and type(value) is str) or (kind == "integer" and type(value) is int) or (kind == "double" and type(value) in (int, float) and math.isfinite(value)), f"invalid native type {t['name']}.{column['name']}")
            record = dict(zip((c["name"] for c in t["columns"]), row))
            key = tuple(record[c["name"]] for c in t["columns"] if c.get("key"))
            if key:
                require(key not in keys, "duplicate native key"); keys.add(key)
            records.append(record)
        rows[t["name"]] = records
    rid = {r["RID"] for r in rows["Resource"]}
    tid = {r["TID"] for r in rows["Tasks"]}
    sid = {r["SID"] for r in rows["System"]}
    site = {r["STID"] for r in rows["Station"]}
    unit = {r["UNID"] for r in rows["Unit"]}
    mtid = {r["MTID"] for r in rows["MissionType"]}
    stype = {r["SUTID"] for r in rows["SubTaskType"]}
    step = {(r["TID"], r["SEQ"]) for r in rows["TaskBreakDown"]}
    for r in rows["TaskBreakDown"]:
        require(r["TID"] in tid and r["SUTID"] in stype, "unresolved native task/step reference")
        require(r["DURN"] > 0 and r["DURND"] is None, "nonpositive/stochastic work")
        integer(r["SEQ"], "SEQ")
    for r in rows["SubTaskResource"]:
        require((r["TID"], r["SEQ"]) in step and r["RID"] in rid, "unresolved native subtask resource reference")
        integer(r["QTY"], "QTY"); require(r["RPROB"] == 1, "stochastic resource probability")
    for r in rows["ResourceAllocation"]:
        require(r["POINT"] in sid and r["RID"] in rid and r["STID"] in site, "unresolved native allocation reference")
        integer(r["RQTY"], "RQTY")
    for r in rows["SubTaskResource"]:
        allocation = [a for a in rows["ResourceAllocation"] if a["RID"] == r["RID"]]
        require(len(allocation) == 1 and r["QTY"] <= allocation[0]["RQTY"], "missing allocation or demand exceeds capacity")
    for r in rows["Resource"]:
        require(r["TYPE"] == "SPECIAL", "unconfirmed native resource type")
    for r in rows["MissionPreparation"]:
        require(r["MTID"] in mtid and r["SID"] in sid and r["STID"] in site and r["TID"] in tid, "unresolved preparation reference")
        require(abs(r["DURN"] - sum(x["DURN"] for x in rows["TaskBreakDown"] if x["TID"] == r["TID"])) < 1e-12, "preparation duration differs from serial sum")
    for r in rows["SystemDeployment"]:
        require(r["SID"] in sid and r["USTID"] in unit, "unresolved deployment reference"); integer(r["QTYPS"], "QTYPS")
    for r in rows["OperationProfile"]:
        require(r["SPRID"] in mtid and r["ITYPE"] == "SCHEDULED", "unresolved schedule or unsupported policy")
    for r in rows["Operations"]:
        require(r["USTID"] in unit and r["PRID"] in {x["PRID"] for x in rows["OperationProfile"]}, "unresolved operation reference")
    for r in rows["Unit"]:
        require(r["STID"] in site, "unresolved unit station")
    active = {"ProblemDescription", "ControlParameters", "GlobalParameters", "Control", "System", "Station", "Unit", "SystemDeployment", "MissionType", "OperationProfile", "OperationParameter", "Operations", "MissionPreparation", "Tasks", "SubTaskType", "TaskBreakDown", "Resource", "ResourceAllocation", "SubTaskResource", "ResultCollection"}
    for name in rows:
        require(name in active or not rows[name], f"unsupported active mechanism: {name}")
    # This is a closed six-candidate contract, not a validator for arbitrary
    # SIMLOX models. Type/reference checks above provide targeted diagnostics;
    # exact membership also rejects hidden flags/distributions in active tables.
    choices = [(c, 2) for c in CASES[:-1]] + [("C03", 1), ("C03", 2)]
    require(any(model == build(c, cap, _check=False) for c, cap in choices),
            "native input differs from the six prepared candidates; unknown mechanism or changed frozen field")
    return rows


def capacity_delta(left, right):
    """Prove the only native input difference is one named allocation's RQTY."""
    a, b = copy.deepcopy(left), copy.deepcopy(right)
    ar, br = (validate_native(x)["ResourceAllocation"] for x in (a, b))
    changed = [(x, y) for x, y in zip(ar, br) if x != y]
    require(len(ar) == len(br) == 2 and len(changed) == 1, "capacity variant changed multiple rows")
    x, y = changed[0]
    require(x["RID"] == y["RID"] == "E-SHARED" and x["RQTY"] == 1 and y["RQTY"] == 2, "wrong capacity delta")
    y["RQTY"] = 1
    require(x == y, "capacity variant changed another allocation field")
    t = writer.table(b, "ResourceAllocation")
    columns = [c["name"] for c in t["columns"]]
    for row in t["instances"][0]["rows"]:
        if row[columns.index("RID")] == "E-SHARED": row[columns.index("RQTY")] = 1
    require(a == b, "capacity variant changed a field outside the one support parameter")
    return {"table": "ResourceAllocation", "key": {"POINT": "RESOURCE-AIR", "RID": "E-SHARED", "STID": "BASE-01"}, "column": "RQTY", "before": 1, "after": 2}


def validate_ledger(ledger, parameters=None):
    """Check an authored deterministic oracle, not native/engine output."""
    p = copy.deepcopy(parameters if parameters is not None else read(ROOT / "parameters.json"))
    validate_parameters(p)
    capacity = ledger["capacity"]
    require(type(capacity) is int and capacity in (1, 2), "ledger capacity")
    pools = {"P-SPECIALIST": 2, "E-SHARED": capacity}
    jobs = ledger["jobs"]
    require(set(jobs) == {m["id"] for m in p["missions"]}, "ledger mission membership")
    allocations = []; waits = 0
    for m in p["missions"]:
        j = jobs[m["id"]]
        require(j["aircraft_id"] == m["aircraft_id"], "ledger aircraft identity")
        require(len(j["steps"]) == 2, "ledger step count")
        available = m["notice_minutes"]
        for s, record in zip(p["steps"], j["steps"]):
            require(set(record) == {"id", "request", "acquire", "release", "demands"}, "ledger step fields")
            require(record["id"] == s["id"] and record["demands"] == s["demands"], "ledger step/demand mismatch")
            for k in ("request", "acquire", "release"): integer(record[k], k)
            require(record["request"] == available and record["acquire"] >= available, "request/serial order violation")
            require(record["release"] - record["acquire"] == s["duration_minutes"], "work duration mismatch")
            waits += record["acquire"] - record["request"]
            available = record["release"]
            allocations.append(record)
        require(j["launch"] == max(m["planned_start_minutes"], available), "launch before readiness or unexplained delay")
        require(j["launch"] < m["planned_start_minutes"] + m["delay_minutes"], "main fixture must avoid deadline tie")
        require(j["return"] == j["launch"] + m["flight_minutes"], "flight duration mismatch")
    moments = sorted({r[k] for r in allocations for k in ("request", "acquire", "release")})
    for at in moments:
        for side in ("left", "right"):
            used = {r: 0 for r in pools}
            for record in allocations:
                active = record["acquire"] < at <= record["release"] if side == "left" else record["acquire"] <= at < record["release"]
                if active:
                    for rid, qty in record["demands"].items(): used[rid] += qty
            require(all(0 <= used[r] <= pools[r] for r in pools), f"capacity conservation at {at}/{side}")
        for waiting in allocations:
            if waiting["request"] <= at < waiting["acquire"]:
                used = {rid: sum(r["demands"].get(rid, 0) for r in allocations if r["acquire"] <= at < r["release"]) for rid in pools}
                require(any(used[rid] + qty > pools[rid] for rid, qty in waiting["demands"].items()), "unexplained idle delay while all demanded resources available")
    area = {rid: sum((r["release"] - r["acquire"]) * r["demands"].get(rid, 0) for r in allocations) for rid in pools}
    require(area == ledger["resource_count_minutes"] == {"P-SPECIALIST": 100, "E-SHARED": 80}, "resource integral mismatch")
    require(waits == ledger["waiting_minutes"] == (20 if capacity == 1 else 0), "expected waiting differs")
    require(ledger["flight_aircraft_minutes"] == sum(j["return"] - j["launch"] for j in jobs.values()) == 120, "flight integral mismatch")
    require(ledger["origin"] == "hand_authored_contract_oracle_not_runtime_output", "oracle mislabeled")
    return {"status": "static_oracle_consistent", "capacity": capacity, "resource_count_minutes": area, "waiting_minutes": waits, "native_verified": False}


def observe_ledger(ledger, at, side="right"):
    """Analytical observation cut only; never cancels work or releases a lease."""
    require(type(at) in (int, float) and math.isfinite(at) and at >= 0, "invalid observation time")
    require(side in ("left", "right"), "observation side")
    validate_ledger(ledger)
    active, waiting = [], []
    for mid, job in ledger["jobs"].items():
        for s in job["steps"]:
            contains = s["acquire"] < at <= s["release"] if side == "left" else s["acquire"] <= at < s["release"]
            if contains:
                active.append({"mission": mid, "step": s["id"], "demands": s["demands"], "release": s["release"]})
            queued = s["request"] < at <= s["acquire"] if side == "left" else s["request"] <= at < s["acquire"]
            if queued: waiting.append({"mission": mid, "step": s["id"], "requested": s["request"]})
    return {"at": at, "side": side, "active": active, "waiting": waiting, "cancelled_by_observation": False}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--case", choices=CASES, default="C03")
    ap.add_argument("--capacity", type=int, choices=(1, 2), default=1)
    ap.add_argument("--output", type=Path)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    if args.check:
        validate_parameters(read(ROOT / "parameters.json"))
        for case, cap in [(c, 2) for c in CASES[:-1]] + [("C03", 1), ("C03", 2)]:
            require((ROOT / "inputs" / f"{case}-capacity-{cap}.json").read_bytes() == encoded(build(case, cap)), "checked input generation mismatch")
        delta = capacity_delta(build("C03", 1), build("C03", 2))
        reports = [validate_ledger(read(ROOT / f"hand-ledger-capacity-{cap}.json")) for cap in (1, 2)]
        print(json.dumps({"status": "prepared_static_validated_native_unverified", "capacity_delta": delta, "hand_ledgers": reports}))
    else:
        require(args.output is not None, "--output required")
        raw = encoded(build(args.case, args.capacity))
        with args.output.open("xb") as stream: stream.write(raw)
        print(json.dumps({"path": str(args.output), "sha256": digest(raw), "status": "candidate_not_native_accepted"}))


if __name__ == "__main__":
    main()
