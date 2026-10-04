"""Read-only author replay of the sealed K04.var04 conflict observations."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import build


CASE = Path(__file__).resolve().parent
RUN = CASE / "runs" / "k04-var04-duplicate-control-key-v100-ssh-20261004-01"
PARENT = CASE.parent / "K04-var01-nested-mdb-include-v1.0.0"
PARENT_RUN = PARENT / "runs" / "k04-var01-nested-mdb-v100-ssh-20261004-01"
checks: list[str] = []


def check(condition: bool, label: str) -> None:
    if not condition:
        raise AssertionError(label)
    checks.append(label)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> None:
    contract = load(CASE / "contract.json")
    invocation = load(RUN / "invocation.json")
    closure = load(RUN / "closure.json")
    outcomes = load(RUN / "outcomes.json")
    steps = load(RUN / "steps.json")
    check(contract["case_id"] == "K04" and contract["variant_id"] == "K04.var04", "case identity")
    check(contract["version"] == "1.0.0-candidate" and contract["publication_state"] == "not_published", "candidate state")
    check(contract["run_id"] == RUN.name == invocation["run_id"] == closure["run_id"] == outcomes["run_id"], "run identity")
    check(contract["dependency"]["package"] == PARENT.name, "parent identity")
    for key, path in {
        "main_input_sha256": PARENT / "main-input.json",
        "level2_station_source_sha256": PARENT / "level2-source.json",
        "closure_sha256": PARENT_RUN / "closure.json",
        "signoff_sha256": PARENT / "cli-scope-signoff-2026-10-04.md",
    }.items():
        check(sha(path) == contract["dependency"][key], f"accepted parent {key}")
    check(load(PARENT_RUN / "closure.json")["error"] is None, "accepted parent run completed")

    check(sha(RUN / "invocation.json") == closure["invocation_sha256"], "invocation seal")
    check(invocation["source_hashes_before"] == closure["source_hashes_before"] == closure["source_hashes_after"], "stable source hashes")
    source_paths = {
        "contract": CASE / "contract.json",
        "control_main": CASE / "control-main-input.json",
        "key_main": CASE / "key-main-input.json",
        "control_mdb_source": CASE / "control-mdb-source.json",
        "key_level1_source": CASE / "key-level1-source.json",
        "key_level2_source": CASE / "key-level2-source.json",
        "accepted_parent_main": PARENT / "main-input.json",
        "accepted_parent_station": PARENT / "level2-source.json",
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
    for name, path in source_paths.items():
        check(path.is_file() and sha(path) == closure["source_hashes_before"].get(name), f"source SHA {name}")
    for name, expected in contract["inputs_sha256"].items():
        check(sha(source_paths[name]) == expected, f"contract input SHA {name}")
    check(sha(CASE / "contract.json") == "060e3f469e375b44b36d4767f9db1d5b74c61473a9b0530bc819ebb29e18b28d", "runner-pinned contract")
    check(closure["error"] is None and outcomes["error"] is None, "no audit error")
    check(closure["publication_state"] == "not_published", "sealed unpublished state")
    check(len(closure["raw"]) == 25, "raw artifact count")
    for name, seal in closure["raw"].items():
        path = RUN / name
        check(path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"], f"raw seal {name}")

    expected = build.build()
    for name, document in expected.items():
        check(load(CASE / name) == document and load(RUN / name) == document, f"frozen parent-derived {name}")
    parent_main = load(PARENT / "main-input.json")
    for arm in ("control", "key"):
        main = load(CASE / f"{arm}-main-input.json")
        include = [table for table in main["model"]["tables"] if table["name"] == "IncludeFiles"]
        check(len(include) == 1 and len(include[0]["instances"]) == 1 and len(include[0]["instances"][0]["rows"]) == 1, f"{arm} one main include")
        check(main["model"]["tables"] != parent_main["model"]["tables"], f"{arm} changed parent IncludeFiles")
        main["model"]["tables"] = parent_main["model"]["tables"]
        check(main == parent_main, f"{arm} parent otherwise unchanged")

    for kind, source_name, db_name in (
        ("control", "control-mdb-source.json", "control.mdb"),
        ("key_level1", "key-level1-source.json", "key-level1.mdb"),
        ("key_level2", "key-level2-source.json", "key-level2.mdb"),
    ):
        source = load(CASE / source_name)["tables"]
        readback = load(RUN / db_name.replace(".mdb", ".readback.json"))
        check(readback["kind"] == kind and readback["process_bitness"] == 32 and readback["driver"] == "Microsoft Access Driver (*.mdb)", f"{kind} x86 ODBC")
        check(readback["tables"] == [table["table"] for table in source], f"{kind} exact user tables")
        for table in source:
            check(readback["contents"][table["table"]] == {"columns": table["columns"], "rows": table["rows"]}, f"{kind} {table['table']} row readback")
        database = RUN / db_name
        check(readback["database_bytes"] == database.stat().st_size and readback["database_sha256"] == sha(database), f"{kind} MDB seal")

    check(len(steps) == 9, "nine guarded steps")
    check([step["name"] for step in steps] == [
        "create_control", "create_key_level2", "create_key_level1",
        "control_import", "control_export", "control_calc",
        "key_import", "key_export", "key_calc",
    ], "step order")
    for step in steps:
        check(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"] is True and step["error"] is None, f"{step['name']} completed with GUI preserved")
    check(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"], "session-zero SSH ancestry")
    check(invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", "host-wide mutex")
    check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, "protected GUI identity")
    check(invocation["association_before"] == closure["association_after"] == "mdb=Microsoft Access Driver (*.mdb)|", "association restored")
    check(invocation["association_during_calc"] == "mdb=Microsoft Access Driver (*.mdb, *.accdb)|", "temporary calc association")

    for arm, code, warnings, mdbs in (
        ("control", "2043", ["108", "108", "126"], ["control.mdb"]),
        ("key", "2013", ["108", "126"], ["key-level1.mdb", "key-level2.mdb"]),
    ):
        log = (RUN / f"{arm}-run.log").read_text(encoding="utf-8-sig", errors="replace")
        outcome = outcomes["arms"][arm]
        check(outcome["sxi_sha256"] == sha(RUN / f"{arm}.sxi") and outcome["run_log_sha256"] == sha(RUN / f"{arm}-run.log"), f"{arm} outcome hashes")
        check((RUN / f"{arm}.sxo").stat().st_size == outcome["sxo_bytes"] == 4, f"{arm} unusable SXO")
        check(re.findall(r"\(error #(\d+)\)", log) == outcome["converter_error_codes"] == [code], f"{arm} sole converter error")
        check(re.findall(r"\(warning #(\d+)\)", log) == outcome["converter_warning_codes"] == warnings, f"{arm} expected warnings")
        check(outcome["converter_summary"] == f"Input conversion completed. Errors: 1, Warnings: {len(warnings)}, Notes: 0", f"{arm} terminal converter summary")
        locations = [log.index("Including data from file: " + str(RUN / mdb).replace("\\", "/")) for mdb in mdbs]
        check(locations == sorted(locations), f"{arm} MDB traversal order")
        check(log.count("Data successfully included") == len(mdbs), f"{arm} successful MDB reads")
        check(not (RUN / f"{arm}-report-raw.json").exists(), f"{arm} no usable report")
        check((RUN / f"{arm}-import.log").is_file() and (RUN / f"{arm}-export.log").is_file() and (RUN / f"{arm}-roundtrip-raw.json").stat().st_size > 1000, f"{arm} import and export")
    control_log = (RUN / "control-run.log").read_text(encoding="utf-8-sig", errors="replace")
    key_log = (RUN / "key-run.log").read_text(encoding="utf-8-sig", errors="replace")
    check("Table already defined: Control" in control_log and "Control, 1 record inserted" in control_log and "Station, 1 record inserted" in control_log, "duplicate Control classification")
    check("Double definition of data for: BASE-01" in key_log and key_log.count("Station, 1 record inserted") == 2 and "IncludeFiles, 1 record inserted" in key_log, "repeated Station key classification")

    result = {
        "schema": "simlox-air-support-author-validation/v1",
        "case_id": "K04",
        "variant_id": "K04.var04",
        "run_id": RUN.name,
        "verdict": "GO — two bounded CLI converter-error observations; NO-GO for usable simulation output or generic conflict rules",
        "checks_passed": len(checks),
        "checks_total": len(checks),
        "closure_sha256": sha(RUN / "closure.json"),
        "evidence": {"control_error": "2043", "key_error": "2013", "sxo_bytes_each": 4},
    }
    (CASE / "author-native-validation-2026-10-04.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(f"{result['verdict']}: {len(checks)}/{len(checks)}")


if __name__ == "__main__":
    main()
