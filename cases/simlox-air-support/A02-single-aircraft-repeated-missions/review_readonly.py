"""Independent read-only A02 source and sealed-run review.

The run paths come from the checked evidence index. No project validator is imported.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A01-single-aircraft-single-mission" / "native-input.json"
CHILD = HERE / "native-input.json"
CONTRACT = HERE / "contract.json"
CONTRACT_SHA256 = "f192c22de44ec20cf8581e2652ce8b4a44fc315acb7998624be340cb5a42a465"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(re.sub(r",(?=\s*[}\]])", "", path.read_text(encoding="utf-8-sig")))


def tables(document: dict, envelope: str) -> dict[str, list[dict]]:
    result = {}
    for item in document[envelope]["tables"]:
        columns = [column["name"] for column in item["columns"]]
        result[item["name"]] = [dict(zip(columns, row, strict=True))
                                for instance in item["instances"] for row in instance["rows"]]
    return result


def source_review() -> list[str]:
    errors = []
    if sha(PARENT) != "8bbd31d05630cc4a44c4b03b715d17e2f4a1ee1601352952089efd3e584f98b7":
        errors.append("published A01 parent hash differs")
    if sha(CHILD) != "84c5cca6c06384b850d2420297a3f5c2f5c553904f123f690190fdb42475e0b8":
        errors.append("A02 input hash differs")
    if sha(CONTRACT) != CONTRACT_SHA256:
        errors.append("A02 frozen contract hash differs")
    before, after = tables(read(PARENT), "model"), tables(read(CHILD), "model")
    if list(before) != list(after):
        errors.append("table order differs from A01")
    changed = [name for name in before if before[name] != after.get(name)]
    if changed != ["OperationProfile"]:
        errors.append(f"changed tables differ: {changed}")
    old, new = before["OperationProfile"], after["OperationProfile"]
    if len(old) != 1 or len(new) != 3 or old != new[:1]:
        errors.append("A02 did not retain the A01 scheduled wave")
    if [row.get("STIM") for row in new] != [8, 20, 32] or any(
            {k: v for k, v in row.items() if k != "STIM"} !=
            {k: v for k, v in old[0].items() if k != "STIM"} for row in new):
        errors.append("new scheduled waves differ except for STIM")
    declared = read(HERE / "parent-diff.json")
    if (declared.get("parent_case") != "A01@1.0.0"
            or declared.get("child_case") != "A02@1.0.0"
            or declared.get("changed_tables") !=
            {"OperationProfile": {"added": new[1:], "removed": []}}):
        errors.append("declared exact A01 parent delta differs")
    return errors


def run_review(entry: dict) -> tuple[list[str], dict]:
    errors = []
    run = Path(entry["directory"])
    run_id = entry["run_id"]
    if not run.is_dir() or run.name != run_id:
        return [f"run directory missing or wrong: {run}"], {}
    for name, record in entry["artifacts"].items():
        path = run / name
        if (not path.is_file() or str(path) != record["path"]
                or path.stat().st_size != record["bytes"] or sha(path) != record["sha256"]):
            errors.append(f"evidence index file mismatch: {name}")
    invocation, closure, manifest = [read(run / name) for name in
                                     ("invocation.json", "closure.json", "run-manifest.json")]
    if (invocation.get("case_id") != "A02" or invocation.get("run_id") != run_id
            or invocation.get("run_dir") != str(run)
            or invocation.get("source_hashes", {}).get("input") != sha(CHILD)
            or invocation.get("source_hashes", {}).get("contract") != sha(CONTRACT)
            or invocation.get("source_hashes", {}).get("validator") !=
            "43b42fbc5f6d2b9ecbeb82b1419224d6a99025c1be5c600dd959f77d362b6354"
            or invocation.get("simlox_exe_sha256") !=
            "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"):
        errors.append("pre-run invocation source/host identity differs")
    if (closure.get("invocation_sha256") != sha(run / "invocation.json")
            or closure.get("run_id") != run_id or closure.get("case_id") != "A02"):
        errors.append("closure invocation identity differs")
    for name, record in closure.get("artifacts", {}).items():
        path = run / name
        if (not path.is_file() or record.get("path") != str(path)
                or path.stat().st_size != record.get("bytes") or sha(path) != record.get("sha256")):
            errors.append(f"closure file mismatch: {name}")
    if (manifest.get("input_sha256") != sha(CHILD)
            or manifest.get("invocation_sha256") != sha(run / "invocation.json")
            or manifest.get("closure_sha256") != sha(run / "closure.json")
            or manifest.get("status") != "cli_behavior_verified"):
        errors.append("native run manifest chain or status differs")
    steps = read(run / "steps.json")
    if ([step.get("name") for step in steps] != ["import", "export", "calc", "jsonreport"]
            or any(step.get("exit_code") != 0 for step in steps)):
        errors.append("native command sequence or exit differs")
    if sha(run / "input.json") != sha(CHILD):
        errors.append("run input differs from checked A02 source")
    original, exported = tables(read(run / "input.json"), "model"), tables(read(run / "roundtrip-raw.json"), "model")
    for name, rows in original.items():
        if rows and rows != exported.get(name):
            errors.append(f"roundtrip business rows differ: {name}")
    log = (run / "model.log").read_text(encoding="utf-8-sig")
    events = [(float(match[1]), match[2].strip()) for line in log.splitlines()
              if (match := re.match(r"^Time:\s*([0-9.eE+\-]+)\s+(.*)$", line))]
    tag, owner = "<BASIC-MISSION,TEACH-UNIT,0,0,0>", "<TEACH-AIR-01,0>"
    checks = {" mission ordered:": [7, 19, 31], " mission created:": [7, 19, 31],
              " mission allocates system:": [7, 19, 31], " mission starting, duration:": [8, 20, 32],
              " mission success:": [10, 22, 34], " mission completed:": [10, 22, 34],
              " mission cancelled:": [], " mission aborted:": []}
    for marker, wanted in checks.items():
        found = [(hour, body) for hour, body in events if marker in body]
        if len(found) != len(wanted) or any(abs(row[0] - hour) > 1e-4 for row, hour in zip(found, wanted)):
            errors.append(f"mission event timeline differs: {marker}: {found}")
    if any(" mission starting, duration: 2 : " + owner not in body
           for _, body in events if " mission starting, duration:" in body):
        errors.append("mission launched with wrong aircraft")
    for marker in (" mission created:", " mission starting, duration:",
                   " mission success:", " mission completed:"):
        found = [body for _, body in events if marker in body]
        if len(found) != 3 or any(not body.startswith(f"<BASIC-MISSION,TEACH-UNIT,0,0,{index}>")
                                  for index, body in enumerate(found)):
            errors.append(f"mission instance identity differs: {marker}")
    report = tables(read(run / "report-raw.json"), "report")
    summary = report.get("ResultSummary", [])
    if len(summary) != 1 or any(summary[0].get(k) != v for k, v in
            {"NREP": 1, "RTILW": 0, "RTIUP": 36, "MSTF": 1, "MSUF": 1}.items()):
        errors.append("native summary differs")
    intervals = report.get("SystemResults", [])
    if len(intervals) != 72:
        errors.append(f"result interval count differs: {len(intervals)}")
    flight = 0
    for index, row in enumerate(intervals):
        hour = index / 2
        expected = {"STINT": hour, "ETINT": hour + .5, "NSYA": 1,
                    "FTMO": int(any(start <= hour < start + 2 for start in (8, 20, 32))),
                    "NSYMO": int(any(start <= hour < start + 2 for start in (8, 20, 32))),
                    "NPSTA": 0}
        if any(row.get(k) != v for k, v in expected.items()):
            errors.append(f"SystemResults interval differs at {index}")
        flight += row.get("FTMO", 0) * .5
    if flight != 6:
        errors.append(f"flight-hour integral differs: {flight}")
    validation = read(run / "validation.json")
    if validation.get("status") != "cli_behavior_verified" or validation.get("differences"):
        errors.append("original source-bound validation did not pass")
    return errors, {"run_id": run_id, "index_files": len(entry["artifacts"]),
                    "closure_raw_files": len(closure.get("artifacts", {})),
                    "nonempty_business_tables": sum(
                        any(any(value not in (None, "") for value in row.values()) for row in rows)
                        for rows in original.values()),
                    "system_intervals": len(intervals), "flight_hours": flight,
                    "hashes": {name: sha(run / name) for name in
                               ("invocation.json", "closure.json", "run-manifest.json",
                                "validation.json", "model.sxi", "model.sxo", "model.log", "report-raw.json")}}


def main() -> None:
    if len(sys.argv) != 1:
        raise SystemExit("usage: review_readonly.py")
    errors = source_review()
    index = read(HERE / "evidence-index.json")
    runs = {}
    for entry in index["runs"]:
        differences, details = run_review(entry)
        errors.extend(f"{entry['run_id']}: {item}" for item in differences)
        runs[entry["run_id"]] = details
    result = {"schema": "simlox-a02-independent-readonly-review/v1",
              "passed": not errors, "differences": errors,
              "reviewer_sha256": sha(HERE / "review_readonly.py"),
              "source_sha256": sha(CHILD), "parent_sha256": sha(PARENT), "runs": runs}
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
