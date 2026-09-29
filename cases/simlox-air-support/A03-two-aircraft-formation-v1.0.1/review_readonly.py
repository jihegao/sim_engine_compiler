"""Independently audit frozen A03 source, native run, and matching GUI artifacts."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A02-single-aircraft-repeated-missions" / "native-input.json"
CHILD = HERE / "native-input.json"
CONTRACT = HERE / "contract.json"
RUN = Path(r"C:\Users\user\Documents\Codex\2026-09-28\simlox-issue18-ssh-current\cases\simlox-air-support\A03-two-aircraft-formation-v1.0.1\runs\a03-v101-ssh-gui-20260929-01")
GUI = Path(r"C:\Users\user\Documents\Codex\2026-09-28\simlox-p1-a03-b7e6945a\cases\simlox-air-support\A03-two-aircraft-formation\runs\gui-review-20260928\gui-calc-20260929")
SOURCE_HASHES = {
    "parent": "84c5cca6c06384b850d2420297a3f5c2f5c553904f123f690190fdb42475e0b8",
    "child": "d7aa35c11a1426de1e74167cc6a3277879f4a2a5814792274490a43dcfe986a4",
    "contract": "123b5391d0b17fdd0b7d61088c883e7cfb891892fe89c7cb85b27e30868ea34d",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(re.sub(r",(?=\s*[}\]])", "", path.read_text(encoding="utf-8-sig")))


def tables(document: dict, envelope: str) -> dict[str, list[dict]]:
    result = {}
    for table in document[envelope]["tables"]:
        if table["name"] in result:
            raise ValueError(f"duplicate table: {table['name']}")
        columns = [column["name"] for column in table["columns"]]
        result[table["name"]] = [dict(zip(columns, row, strict=True))
                                 for instance in table["instances"] for row in instance["rows"]]
    return result


def audit() -> dict:
    errors = []
    for label, path in (("parent", PARENT), ("child", CHILD), ("contract", CONTRACT)):
        if sha(path) != SOURCE_HASHES[label]:
            errors.append(f"{label} source hash differs")
    contract = read(CONTRACT)
    if (contract.get("parent_input_sha256") != sha(PARENT)
            or contract.get("input_sha256") != sha(CHILD)):
        errors.append("contract parent or child identity differs")
    before, after = tables(read(PARENT), "model"), tables(read(CHILD), "model")
    changed = [name for name in before if before[name] != after.get(name)]
    if (list(before) != list(after)
            or set(changed) != {"MissionType", "OperationProfile", "ProblemDescription", "SystemDeployment"}):
        errors.append(f"A02-to-A03 table delta differs: {changed}")
    declared = read(HERE / "parent-diff.json")
    if (declared.get("parent_input_sha256") != sha(PARENT)
            or set(declared.get("changed_tables", {})) != set(changed)):
        errors.append("declared parent delta differs")
    for name in changed:
        claim = declared["changed_tables"][name]
        if claim.get("parent_rows") != before[name] or claim.get("child_rows") != after[name]:
            errors.append(f"declared {name} rows differ")
    if not RUN.is_dir() or RUN.name != "a03-v101-ssh-gui-20260929-01":
        raise ValueError("sealed A03 run directory missing")
    invocation, closure, manifest = (read(RUN / name) for name in
                                     ("invocation.json", "closure.json", "run-manifest.json"))
    if (invocation.get("input_sha256") != sha(CHILD)
            or invocation.get("contract_sha256") != sha(CONTRACT)
            or invocation.get("validator_sha256") != sha(HERE / "validate.py")
            or invocation.get("strict_validator_sha256") != sha(HERE / "validate_strict.py")
            or invocation.get("runner_sha256") != sha(HERE / "run_native_ssh.ps1")
            or invocation.get("execution_mode") != "ssh_cli_v1"
            or invocation.get("session_id") != 0
            or "sshd.exe" not in [s.lower() for s in invocation.get("ssh_ancestor_names", [])]
            or invocation.get("coexisting_gui", {}).get("pid") != 13340):
        errors.append("native invocation source, SSH or GUI identity differs")
    raw = closure.get("raw", {})
    if len(raw) != 11 or closure.get("input_sha256") != sha(CHILD):
        errors.append("raw closure inventory or input differs")
    for name, record in raw.items():
        path = RUN / name
        if (not path.is_file() or path.stat().st_size != record["bytes"]
                or sha(path) != record["sha256"]):
            errors.append(f"raw closure file differs: {name}")
    if (manifest.get("closure_sha256") != sha(RUN / "closure.json")
            or manifest.get("validation_sha256") != sha(RUN / "validation.json")
            or manifest.get("strict_validation_sha256") != sha(RUN / "strict-validation.json")):
        errors.append("native manifest hash chain differs")
    for name in ("validation.json", "strict-validation.json"):
        saved = read(RUN / name)
        if saved.get("passed") is not True or saved.get("differences") != []:
            errors.append(f"saved {name} did not pass")
    steps = read(RUN / "steps.json")
    if ([step.get("name") for step in steps] != ["import", "export", "calc", "jsonreport"]
            or any(step.get("exit_code") != 0 for step in steps)):
        errors.append("native command sequence or exit differs")
    input_rows = tables(read(RUN / "input.json"), "model")
    exported = tables(read(RUN / "roundtrip-raw.json"), "model")
    if sha(RUN / "input.json") != sha(CHILD):
        errors.append("run input differs from checked source")
    for name, rows in input_rows.items():
        if rows and rows != exported.get(name):
            errors.append(f"roundtrip business rows differ: {name}")
    log = (RUN / "model.log").read_text(encoding="utf-8-sig")
    events = [(float(m[1]), m[2].strip()) for line in log.splitlines()
              if (m := re.match(r"^Time:\s*([0-9.eE+\-]+)\s+(.*)$", line))]
    aircraft = ("<TEACH-AIR-01,0>", "<TEACH-AIR-01,1>")
    expected_events = {
        " mission ordered:": (7,), " mission created:": (7,),
        " mission allocates system:": (7, 7), " mission starting, duration:": (8,),
        " mission success:": (10,), " mission completed:": (10,),
        " mission cancelled:": (), " mission aborted:": (),
    }
    for marker, wanted in expected_events.items():
        found = tuple(hour for hour, body in events if marker in body)
        if found != wanted:
            errors.append(f"event chronology differs: {marker}: {found}")
    allocated = [body for _, body in events if " mission allocates system:" in body]
    if len(allocated) != 2 or any(aircraft[i] not in allocated[i] for i in range(2)):
        errors.append("two distinct aircraft were not allocated")
    if not any(" mission starting, duration: 2 : " + ",".join(aircraft) in body
               for _, body in events):
        errors.append("formation launch identity or duration differs")
    report = tables(read(RUN / "report-raw.json"), "report")
    summary = report.get("ResultSummary", [])
    if len(summary) != 1 or any(summary[0].get(k) != v for k, v in
            {"NREP": 1, "RTILW": 0, "RTIUP": 36, "MSTF": 1, "MSUF": 1}.items()):
        errors.append("native result summary differs")
    intervals = report.get("SystemResults", [])
    if len(intervals) != 72:
        errors.append("SystemResults interval count differs")
    for i, row in enumerate(intervals):
        hour = i / 2
        wanted = {"STINT": hour, "ETINT": hour + .5, "NSYA": 2,
                  "FTMO": int(8 <= hour < 10), "NSYMO": 2 * int(8 <= hour < 10),
                  "NPSTA": 0}
        if any(row.get(k) != v for k, v in wanted.items()):
            errors.append(f"SystemResults interval differs at {i}")
    gui_sxi = GUI / "A03-v101-ssh-01-gui-calc.sxi"
    gui_log = GUI / "A03-v101-ssh-01-gui-calc.log"
    screen = GUI / "a01-a02-a03-system-availability-20260929.png"
    if sha(gui_sxi) != sha(RUN / "model.sxi") or sha(gui_log) != sha(RUN / "model.log"):
        errors.append("matching-input GUI SXI or event log differs")
    if sha(screen) != "47b524b74d40abbe8cedf2b761e8dc52ba51de67a926d4b2a6d1c0d55c29f684":
        errors.append("GUI comparison screenshot hash differs")
    return {"schema": "simlox-a03-independent-readonly-review/v1",
            "passed": not errors, "differences": errors,
            "source_sha256": {label: sha(path) for label, path in
                              (("parent", PARENT), ("child", CHILD), ("contract", CONTRACT))},
            "run_id": RUN.name, "run_directory": str(RUN),
            "raw_closure_files": len(raw), "nonempty_business_tables": sum(
                any(any(value not in (None, "") for value in row.values()) for row in rows)
                for rows in input_rows.values()),
            "system_intervals": len(intervals), "formation_aircraft_hours": 4,
            "hashes": {name: sha(RUN / name) for name in
                       ("invocation.json", "closure.json", "model.sxi", "model.sxo", "model.log", "report-raw.json")},
            "gui_sxi_sha256": sha(gui_sxi), "gui_log_sha256": sha(gui_log),
            "gui_screenshot_sha256": sha(screen),
            "reviewer_sha256": sha(HERE / "review_readonly.py")}


if __name__ == "__main__":
    result = audit()
    print(json.dumps(result, indent=2))
    if not result["passed"]:
        raise SystemExit(1)
