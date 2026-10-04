"""Read-only author replay of the K05.var02 default-instance ODBC null merge."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import build


CASE = Path(__file__).resolve().parent
RUN = CASE / "runs" / "k05-var02-odbc-null-v101-ssh-20261004-01"
PARENT = CASE.parent / "K02-var01-json-structure-v1.0.1"
PARENT_RUN = PARENT / "runs" / "k02-var01-named-v101-ssh-20261004-01"
checks: list[str] = []


def check(condition: bool, label: str) -> None:
    if not condition:
        raise AssertionError(label)
    checks.append(label)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def table(document, name: str):
    found = [entry for entry in document["model"]["tables"] if entry["name"] == name]
    check(len(found) == 1, f"unique {name} table")
    return found[0]


def main() -> None:
    contract = load(CASE / "contract.json")
    invocation = load(RUN / "invocation.json")
    closure = load(RUN / "closure.json")
    outcome = load(RUN / "outcome.json")
    steps = load(RUN / "steps.json")
    check(contract["case_id"] == "K05" and contract["variant_id"] == "K05.var02", "case identity")
    check(contract["version"] == "1.0.1-candidate" and contract["publication_state"] == "not_published", "candidate version")
    check(contract["run_id"] == RUN.name == invocation["run_id"] == closure["run_id"], "run identity")
    check(contract["dependency"]["package"] == PARENT.name, "accepted parent package")
    parent_paths = {
        "named_input_sha256": PARENT / "named-input.json",
        "native_sxi_sha256": PARENT_RUN / "model.sxi",
        "native_roundtrip_sha256": PARENT_RUN / "roundtrip-raw.json",
        "closure_sha256": PARENT_RUN / "closure.json",
        "signoff_sha256": PARENT / "cli-scope-signoff-2026-10-04.md",
    }
    for key, path in parent_paths.items():
        check(path.is_file() and sha(path) == contract["dependency"][key], f"accepted parent {key}")
    check(load(PARENT_RUN / "closure.json")["error"] is None, "accepted parent completed")
    check(sha(CASE / "contract.json") == "f2f824a595951436f0f37b00c7cd70cd56f18fe7390f1b89f5a66261126ada78", "runner-pinned contract")
    check(sha(RUN / "invocation.json") == closure["invocation_sha256"], "invocation seal")
    check(invocation["source_hashes_before"] == closure["source_hashes_before"] == closure["source_hashes_after"], "stable source map")
    source_paths = {
        "contract": CASE / "contract.json",
        "baseline_input": CASE / "baseline-input.json",
        "database_source": CASE / "database-source.json",
        "accepted_parent_input": PARENT / "named-input.json",
        "accepted_parent_sxi": PARENT_RUN / "model.sxi",
        "accepted_parent_roundtrip": PARENT_RUN / "roundtrip-raw.json",
        "accepted_parent_closure": PARENT_RUN / "closure.json",
        "accepted_parent_signoff": PARENT / "cli-scope-signoff-2026-10-04.md",
        "exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
        "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
        "build.py": CASE / "build.py",
        "create_mdb_x86.ps1": CASE / "create_mdb_x86.ps1",
        "run_native_ssh.ps1": CASE / "run_native_ssh.ps1",
        "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
        "powershell_x86": Path(r"C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe"),
    }
    for key, path in source_paths.items():
        check(path.is_file() and sha(path) == closure["source_hashes_before"][key], f"source SHA {key}")
    for key, value in contract["inputs_sha256"].items():
        check(sha(source_paths[key]) == value, f"contract input SHA {key}")
    check(closure["error"] is None and outcome["error"] is None and closure["publication_state"] == "not_published", "successful unpublished closure")
    check(len(closure["raw"]) == 26, "26 raw artifacts")
    for name, seal in closure["raw"].items():
        path = RUN / name
        check(path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"], f"raw seal {name}")

    built = build.build()
    for name, document in built.items():
        check(load(CASE / name) == document and load(RUN / name) == document, f"frozen generated {name}")
    parent = load(PARENT / "named-input.json")
    baseline = load(CASE / "baseline-input.json")
    parent_station = table(parent, "Station")
    baseline_station = table(baseline, "Station")
    check(baseline_station["columns"] == parent_station["columns"], "Station schema unchanged")
    check(baseline_station["instances"] == [{"instance_name": "", "rows": [parent_station["instances"][0]["rows"][0], parent_station["instances"][1]["rows"][0]]}], "two K02 business rows flattened without value change")
    for name in [t["name"] for t in parent["model"]["tables"] if t["name"] != "Station"]:
        check(table(parent, name) == table(baseline, name), f"unchanged parent {name}")
    check(len(parent["model"]["tables"]) == len(baseline["model"]["tables"]) == 31, "31 parent tables")

    readback = load(RUN / "input.readback.json")
    database = RUN / "input.mdb"
    check(readback["process_bitness"] == 32 and readback["driver"] == "Microsoft Access Driver (*.mdb)", "x86 MDB readback")
    check(readback["tables"] == ["Station"] and readback["columns"] == ["STID", "DESCR", "QTY", "TYPE"], "only authored Station table")
    check(readback["rows"] == [["BASE-01", "ODBC merged teaching base", None, None]], "database null row")
    check(readback["database_bytes"] == database.stat().st_size and readback["database_sha256"] == sha(database), "MDB bytes match readback")
    dsn = load(RUN / "dsn-observation.json")
    check(dsn["name"] == contract["user_dsn"] == invocation["dsn_name"] and dsn["driver"] == invocation["dsn_driver"], "frozen task DSN identity")
    check(dsn["database_path"] == str(database) and dsn["database_sha256"] == sha(database), "DSN points at sealed MDB")
    check(dsn["select_row"] == readback["rows"][0], "64-bit DSN row query")
    check(invocation["dsn_before"] == closure["dsn_after"] == "absent" and outcome["dsn_removed_before_calc"] is True, "task DSN removed before calculation")

    names = [s["name"] for s in steps]
    check(names == ["baseline_import", "baseline_export", "baseline_calc", "baseline_jsonreport", "database_create", "odbc_import", "merged_export", "calc", "jsonreport"], "nine step order")
    for step in steps:
        check(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"] is True and step["error"] is None, f"{step['name']} guarded completion")
    check(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"], "session-zero SSH")
    check(invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", "host-wide queue")
    check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, "protected GUI identity")
    check(invocation["association_before"] == closure["association_after"] == "mdb=Microsoft Access Driver (*.mdb)|", "MDB association unchanged")
    check(outcome["baseline"] == outcome["import_export"] == outcome["calc"] == outcome["report"] == "completed", "all outcome stages completed")

    base_export = load(RUN / "base-roundtrip-raw.json")
    merged_export = load(RUN / "roundtrip-raw.json")
    base_station = table(base_export, "Station")
    merged_station = table(merged_export, "Station")
    check(base_station["instances"] == baseline_station["instances"], "native baseline Station exact")
    check(len(merged_station["instances"]) == 1 and merged_station["instances"][0]["instance_name"] == "", "one default merged Station instance")
    old_rows = base_station["instances"][0]["rows"]
    new_rows = merged_station["instances"][0]["rows"]
    check(len(old_rows) == len(new_rows) == 2, "two Station rows and no duplicate key")
    check(new_rows[0][:4] == ["BASE-01", "ODBC merged teaching base", 1, "WS"], "key update with null QTY/TYPE preservation")
    check(new_rows[0][4:] == old_rows[0][4:] and new_rows[1] == old_rows[1], "other Station fields unchanged")
    check([r[0] for r in new_rows] == ["BASE-01", "K02-NAMED"], "Station key order unchanged")
    check(base_station["columns"] == merged_station["columns"], "Station columns unchanged")
    check(len(base_export["model"]["tables"]) == len(merged_export["model"]["tables"]) == 31, "native 31-table topology")
    for name in [t["name"] for t in base_export["model"]["tables"] if t["name"] != "Station"]:
        check(table(base_export, name) == table(merged_export, name), f"merged non-Station table {name} unchanged")
    check("Station, 1 record updated" in (RUN / "import.log").read_text(encoding="utf-8-sig") and "Data successfully imported" in (RUN / "import.log").read_text(encoding="utf-8-sig"), "native ODBC key update log")
    for prefix in ("base-", ""):
        log = (RUN / f"{prefix}run.log").read_text(encoding="utf-8-sig", errors="replace")
        check("Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in log, f"{prefix}zero-error converter")
        check(re.findall(r"\(warning #(\d+)\)", log) == ["108", "126"] and not re.search(r"\(error #", log), f"{prefix}reviewed warnings only")
        check((RUN / f"{prefix[:-1] if prefix else 'model'}.sxo").stat().st_size > 4, f"{prefix}usable SXO")
    for name in ("base.log", "model.log"):
        check((RUN / name).read_bytes() == (PARENT_RUN / "model.log").read_bytes(), f"{name} accepted event log byte equality")
    for name in ("base-report-raw.json", "report-raw.json"):
        check((RUN / name).read_bytes() == (PARENT_RUN / "report-raw.json").read_bytes(), f"{name} accepted report byte equality")
    event = (RUN / "model.log").read_text(encoding="utf-8-sig")
    for marker in ("Time: 7 <TEACH-UNIT> mission ordered: BASIC-MISSION", "Time: 8 <BASIC-MISSION", "mission starting, duration: 3", "Time: 11 <BASIC-MISSION", "mission success", "systems ready: 1 :<TEACH-AIR-01,0>"):
        check(marker in event, f"accepted individual event {marker}")
    check("no failures" in event and "no PMTasks" in event, "no failure or PM event")

    result = {
        "schema": "simlox-air-support-author-validation/v1",
        "case_id": "K05",
        "variant_id": "K05.var02",
        "version": "1.0.1",
        "run_id": RUN.name,
        "verdict": "GO — one default-Station ODBC key update preserves two imported null fields",
        "checks_passed": len(checks),
        "checks_total": len(checks),
        "closure_sha256": sha(RUN / "closure.json"),
        "evidence": {
            "raw_file_count": len(closure["raw"]),
            "baseline_event_sha256": sha(RUN / "base.log"),
            "merged_event_sha256": sha(RUN / "model.log"),
            "baseline_report_sha256": sha(RUN / "base-report-raw.json"),
            "merged_report_sha256": sha(RUN / "report-raw.json"),
            "dsn_after": closure["dsn_after"],
        },
    }
    (CASE / "author-native-validation-2026-10-04.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"{result['verdict']}: {len(checks)}/{len(checks)}")


if __name__ == "__main__":
    main()
