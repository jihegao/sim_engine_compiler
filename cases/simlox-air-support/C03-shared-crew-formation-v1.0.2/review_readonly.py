"""Independent, standard-library-only review of C03 final native runs."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "C02-joint-resources-v1.0.2" / "inputs" / "single-both.json"
FORMATION = HERE.parent / "A03-two-aircraft-formation-v1.0.1" / "native-input.json"
RUNS = {"staffing-2": "c03-v102-staff2-ssh-20260929-04",
        "staffing-1": "c03-v102-staff1-ssh-20260929-02",
        "staffing-0": "c03-v102-staff0-ssh-20260929-02"}
CAPACITY = {"staffing-2": 2, "staffing-1": 1, "staffing-0": 0}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(re.sub(r",(?=\s*[}\]])", "", path.read_text(encoding="utf-8-sig")))


def tables(doc: dict, envelope: str) -> dict[str, list[dict]]:
    out = {}
    for item in doc[envelope]["tables"]:
        if item["name"] in out:
            raise ValueError(f"duplicate table {item['name']}")
        names = [column["name"] for column in item["columns"]]
        out[item["name"]] = [dict(zip(names, row, strict=True))
                             for instance in item["instances"] for row in instance["rows"]]
    return out


def source_review() -> list[str]:
    errors = []
    contract = read(HERE / "contract.json")
    if (sha(PARENT) != contract["parent_input_sha256"]
            or sha(FORMATION) != contract["formation_parent_input_sha256"]):
        errors.append("published source parent fingerprint differs")
    parent = tables(read(PARENT), "model")
    formation = tables(read(FORMATION), "model")
    if (formation["SystemDeployment"][0]["QTYPS"] != 2
            or formation["MissionType"][0]["NOS"] != 2
            or formation["MissionType"][0]["MNOS"] != 2):
        errors.append("accepted A03 formation fields differ")
    variants = {}
    changed_expected = {"ProblemDescription", "Unit", "SystemDeployment", "MissionType",
                        "OperationProfile", "MissionPreparation", "Resource",
                        "ResourceAllocation", "SubTaskResource"}
    for variant, capacity in CAPACITY.items():
        source = HERE / "inputs" / f"{variant}.json"
        diff_path = HERE / "parent-diffs" / f"{variant}.json"
        spec = contract["variants"][variant]
        if sha(source) != spec["input_sha256"] or sha(diff_path) != spec["parent_diff_sha256"]:
            errors.append(f"{variant}: source or parent diff fingerprint differs")
        child, diff = tables(read(source), "model"), read(diff_path)
        variants[variant] = child
        changed = {name for name in parent if parent[name] != child.get(name)}
        if list(parent) != list(child) or changed != changed_expected:
            errors.append(f"{variant}: changed model table set differs")
        if (diff.get("parent_input_sha256") != sha(PARENT)
                or diff.get("child_input_sha256") != sha(source)
                or set(diff.get("changed_tables_only", [])) != changed):
            errors.append(f"{variant}: parent diff identity differs")
        for name in changed:
            claim = diff["tables"].get(name)
            if claim != {"parent_rows": parent[name], "child_rows": child[name]}:
                errors.append(f"{variant}: exact {name} delta differs")
        if (child["SystemDeployment"][0]["QTYPS"] != 2
                or child["MissionType"][0]["NOS"] != 2
                or child["MissionType"][0]["MNOS"] != 2
                or child["MissionType"][0]["DURN"] != 1
                or child["MissionType"][0]["NOPER"] != .5
                or child["OperationProfile"][0]["STIM"] != 8
                or child["OperationProfile"][0]["DTIM"] != 1
                or child["MissionPreparation"][0]["DURN"] != .5
                or len(child["Resource"]) != 1 or child["Resource"][0]["RID"] != "P-CREW"
                or len(child["ResourceAllocation"]) != 1
                or child["ResourceAllocation"][0]["RQTY"] != capacity
                or child["ResourceAllocation"][0]["POINT"] != child["Control"][0]["APID"]
                or child["ResourceAllocation"][0]["RID"] != "P-CREW"
                or [(r["RID"], r["QTY"]) for r in child["SubTaskResource"]] != [("P-CREW", 1)]):
            errors.append(f"{variant}: shared-pool formation model differs")
    common = variants["staffing-2"]
    for variant in ("staffing-1", "staffing-0"):
        for name in common:
            if name == "ResourceAllocation":
                base, changed = common[name][0], variants[variant][name][0]
                if {k: v for k, v in base.items() if k != "RQTY"} != {
                        k: v for k, v in changed.items() if k != "RQTY"}:
                    errors.append(f"{variant}: capacity variant changes other allocation fields")
            elif common[name] != variants[variant][name]:
                errors.append(f"{variant}: capacity variant changes {name}")
    return errors


def run_review(variant: str, run_id: str) -> tuple[list[str], dict]:
    errors = []
    run = HERE / "runs" / run_id
    cap = CAPACITY[variant]
    invocation, closure, manifest = (read(run / name) for name in
                                     ("invocation.json", "closure.json", "run-manifest.json"))
    if (invocation.get("case_id") != "C03" or invocation.get("run_id") != run_id
            or invocation.get("variant_id") != variant
            or invocation.get("input_sha256") != sha(HERE / "inputs" / f"{variant}.json")
            or invocation.get("contract_sha256") != sha(HERE / "contract.json")
            or invocation.get("validator_sha256") != sha(HERE / "validate.py")
            or invocation.get("builder_sha256") != sha(HERE / "build.py")
            or invocation.get("runner_sha256") != sha(HERE / "run_native_ssh.ps1")
            or invocation.get("launcher_sha256") != sha(HERE / "invoke_loopback.ps1")
            or invocation.get("parent_input_sha256") != sha(PARENT)
            or invocation.get("formation_parent_input_sha256") != sha(FORMATION)
            or invocation.get("parent_diff_sha256") != sha(HERE / "parent-diffs" / f"{variant}.json")
            or invocation.get("session_id") != 0
            or "sshd.exe" not in invocation.get("ssh_ancestor_names", [])
            or invocation.get("coexisting_gui", {}).get("pid") != 13340):
        errors.append("native invocation source, SSH or GUI identity differs")
    raw = closure.get("raw", {})
    if (len(raw) != 11 or closure.get("invocation_sha256") != sha(run / "invocation.json")
            or closure.get("run_id") != run_id or closure.get("variant_id") != variant):
        errors.append("raw closure inventory or identity differs")
    for name, record in raw.items():
        path = run / name
        if (not path.is_file() or path.stat().st_size != record["bytes"]
                or sha(path) != record["sha256"]):
            errors.append(f"raw file hash/size differs: {name}")
    if (manifest.get("invocation_sha256") != sha(run / "invocation.json")
            or manifest.get("closure_sha256") != sha(run / "closure.json")
            or manifest.get("validation_sha256") != sha(run / "validation.json")):
        errors.append("native manifest hash chain differs")
    validation = read(run / "validation.json")
    if validation.get("passed") is not True or validation.get("differences") != []:
        errors.append("source-bound native validator did not pass")
    steps = read(run / "steps.json")
    if ([s.get("name") for s in steps] != ["import", "export", "calc", "jsonreport"]
            or any(s.get("exit_code") != 0 or s.get("coexisting_gui_present_after") is not True
                   for s in steps)):
        errors.append("native steps or GUI coexistence differ")
    run_log = (run / "run.log").read_text(encoding="utf-8-sig")
    conversion = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", run_log)
    warnings = re.findall(r"\(warning #(\d+)\)", run_log)
    if conversion is None or conversion.group(1, 2) != ("0", "2") or sorted(warnings) != ["108", "126"]:
        errors.append("native conversion errors or warnings differ")
    original, exported = tables(read(run / "input.json"), "model"), tables(read(run / "roundtrip-raw.json"), "model")
    if sha(run / "input.json") != sha(HERE / "inputs" / f"{variant}.json"):
        errors.append("run input differs from source")
    for name, rows in original.items():
        meaningful = [row for row in rows if any(v not in (None, "") for v in row.values())]
        echoed = [row for row in exported.get(name, []) if any(v not in (None, "") for v in row.values())]
        if meaningful != echoed:
            errors.append(f"roundtrip business rows differ: {name}")
    log = (run / "model.log").read_text(encoding="utf-8-sig")
    events = [(n, float(m[1]), m[2].strip()) for n, line in enumerate(log.splitlines(), 1)
              if (m := re.match(r"^Time:\s*([0-9.eE+\-]+)\s+(.*)$", line))]
    owners = ("<TEACH-AIR-01,0>", "<TEACH-AIR-01,1>")
    tag = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
    def matching(marker: str):
        return [row for row in events if marker in row[2]]
    def check(marker: str, hours: tuple[float, ...]):
        found = matching(marker)
        if tuple(row[1] for row in found) != hours:
            errors.append(f"event timeline differs: {marker}: {found}")
        return found
    check(" mission ordered:", (7.5,))
    check(" mission allocates system:", (7.5, 7.5))
    allocation = matching(" mission allocates system:")
    if len(allocation) == 2 and {owner for row in allocation for owner in owners if owner in row[2]} != set(owners):
        errors.append("two distinct aircraft not allocated")
    check(" requests resources", (7.5, 7.5))
    requests = matching(" requests resources")
    if len(requests) == 2 and {owner for row in requests for owner in owners if owner in row[2]} != set(owners):
        errors.append("two distinct aircraft did not request crew")
    booked = check(" books resources", (7.5, 7.5) if cap == 2 else (7.5, 8) if cap == 1 else ())
    leased = check(" allocated to maintenance task:", (7.5, 7.5) if cap == 2 else (7.5, 8) if cap == 1 else ())
    worked = check(" starts performing,", (7.5, 7.5) if cap == 2 else (7.5, 8) if cap == 1 else ())
    freed = check(" frees resources", (8, 8) if cap == 2 else (8, 8.5) if cap == 1 else ())
    released = check(" deallocated from  maintenance task:", (8, 8) if cap == 2 else (8, 8.5) if cap == 1 else ())
    check(" resource received", (8,) if cap == 1 else ())
    check(" resource waiting stopped", (8.5, 8.5) if cap == 0 else ())
    done = [row for row in events if "subtask" in row[2] and row[2].endswith(" completed")]
    if tuple(row[1] for row in done) != ((8, 8) if cap == 2 else (8, 8.5) if cap == 1 else ()):
        errors.append("per-aircraft preparation completion differs")
    if cap:
        if len(worked) == 2 and {owner for row in worked for owner in owners if owner in row[2]} != set(owners):
            errors.append("work owner bijection differs")
        for i in range(min(len(booked), len(leased), len(worked), 2)):
            owner = next((o for o in owners if o in worked[i][2]), None)
            if (owner is None or owner not in booked[i][2]
                    or not booked[i][0] < leased[i][0] < worked[i][0]
                    or "planned to last for 0.5 hours" not in worked[i][2]):
                errors.append(f"lease-before-work owner chain differs at {i}")
        for i in range(min(len(freed), len(released), 2)):
            if freed[i][0] >= released[i][0]:
                errors.append(f"release-before-free at {i}")
        if cap == 1 and len(released) == len(leased) == 2 and released[0][0] >= leased[1][0]:
            errors.append("waiting owner received crew before first release")
    launch = 8 if cap == 2 else 8.5 if cap == 1 else None
    check(" mission starting, duration: 1 : " + ",".join(owners), (launch,) if launch else ())
    check(" mission success:", (launch + 1,) if launch else ())
    check(" mission completed: " + ",".join(owners), (launch + 1,) if launch else ())
    check(" mission cancelled:", (8.5,) if cap == 0 else ())
    for owner in owners:
        ended = [row for row in events if row[2] == owner + " preparation ended, mission: " + tag]
        expected_end = 8.5 if cap == 0 or cap == 1 and owner == owners[1] else 8
        if tuple(row[1] for row in ended) != (expected_end,):
            errors.append(f"{owner} preparation end differs")
    report = tables(read(run / "report-raw.json"), "report")
    summary = report.get("ResultSummary", [])
    if len(summary) != 1 or any(summary[0].get(k) != v for k, v in
            {"NREP": 1, "RTILW": 0, "RTIUP": 36, "MSTF": int(cap > 0), "MSUF": int(cap > 0)}.items()):
        errors.append("native summary differs")
    system, resource = report.get("SystemResults", []), report.get("ResourceResults", [])
    if len(system) != 72 or len(resource) != 72:
        errors.append("72 system/resource intervals not present")
    for i, (s, r) in enumerate(zip(system, resource)):
        hour = i / 2
        flying = int(launch is not None and launch <= hour < launch + 1)
        prep = 2 if hour == 7.5 else 1 if cap == 1 and hour == 8 else 2 if cap == 0 and hour == 8 else 0
        busy = 2 if cap == 2 and hour == 7.5 else 1 if cap == 1 and hour in (7.5, 8) else 0
        waiting = 1 if cap == 1 and hour == 7.5 else 2 if cap == 0 and hour in (7.5, 8) else 0
        expected_system = {"STINT": hour, "ETINT": hour + .5, "NSYA": 2,
                           "NSYMO": 2 * flying, "FTMO": flying, "NSYMP": prep,
                           "NPSTA": 2 if hour == 7.5 else 0,
                           "NPSUC": 2 if cap == 2 and hour == 8 else
                                     1 if cap == 1 and hour in (8, 8.5) else 0}
        expected_resource = {"STINT": hour, "ETINT": hour + .5,
                             "NR": cap, "NRUM": busy, "NRW": waiting}
        if any(s.get(k) != v for k, v in expected_system.items()):
            errors.append(f"system interval differs: {i}")
        if any(abs(r.get(k, -100) - v) > 1e-5 for k, v in expected_resource.items()):
            errors.append(f"resource interval differs: {i}")
    return errors, {"run_id": run_id, "raw_closure_files": len(raw),
                    "nonempty_business_tables": sum(any(any(v not in (None, "") for v in row.values())
                                                        for row in rows) for rows in original.values()),
                    "system_intervals": len(system), "resource_intervals": len(resource),
                    "launch_hour": launch, "cancellation_hour": 8.5 if cap == 0 else None,
                    "hashes": {name: sha(run / name) for name in
                               ("invocation.json", "closure.json", "validation.json", "run-manifest.json",
                                "model.sxi", "model.sxo", "model.log", "report-raw.json")}}


if __name__ == "__main__":
    errors = source_review()
    runs = {}
    for variant, run_id in RUNS.items():
        differences, result = run_review(variant, run_id)
        errors.extend(f"{variant}: {item}" for item in differences)
        runs[variant] = result
    result = {"schema": "simlox-c03-independent-readonly-review/v1",
              "passed": not errors, "differences": errors,
              "parent_sha256": sha(PARENT), "formation_parent_sha256": sha(FORMATION),
              "contract_sha256": sha(HERE / "contract.json"),
              "reviewer_sha256": sha(HERE / "review_readonly.py"), "runs": runs}
    print(json.dumps(result, indent=2))
    if errors:
        raise SystemExit(1)
