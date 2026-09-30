"""Read-only independent replay of the A13 unfinished-precedent #204 pair.

No imports from the author's builder, runner, checker, or validator. Only this
review directory is written; sealed native runs are read without modification.
"""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parents[1]
AIR = HERE.parent
PARENT = AIR / "A13-start-dependence-v1.0.0" / "dependent-input.json"
PRIOR = AIR / "A13-var04-unfinished-precedent-v1.0.1"
RUNS = {
    "unfinished-control": "a13-var04-unfinished-control-v102-20261001-01",
    "unfinished-dependency": "a13-var04-unfinished-dependency-v102-20261001-01",
}
FROZEN = {
    "parent": "954e40c17ba0f34f041c405076195fa2d1ac8b471d65e7de4b441e51fa8a5246",
    "contract": "a572cc1786d0c630ee47d302ea1f37b89e30f3e6066c3f5fedebc7560eea30bf",
    "builder": "1eb53beb80ac37df80519830463e9f316dc95d99a3d1dc7016544f1ec2637f6e",
    "exact_diff": "4b77e8da05b4a6eed522fada0e3678708a6ad878141d9a846e42d126df21a009",
    "diff_checker": "60faa66bcb9439d6ee344a0e7b9db7341fb8bacff9379b62eecba6ba96d42d5a",
    "checker": "0f949f5b2f22f08f1cf3cbcaea7824f06b1f63acd8ab776b4ff3460208987b48",
    "runner_script": "f3f213487de6b198fb161e0ddb975c042ff9247f8b6f2840f3e5df7530aa9327",
    "python": "372c2eae555b344520bf147be0096e009069aeca4e7f78d6aecea6d53158056a",
    "simlox_exe": "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0",
    "manual": "39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3",
    "dictionary": "11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0",
    "unfinished-control": "f2fe8b8ed9f90709ed757cfba34ceee9c27a30a4c87fa6a5b36cf4dcf69039d5",
    "unfinished-dependency": "f93cb837c42d0c0b0f49e43f142f390c4c03b936fc685f21dc79ee4e9a2ef513",
}
FILES = {
    "parent": PARENT,
    "contract": HERE / "contract.json",
    "builder": HERE / "build.py",
    "exact_diff": HERE / "exact-diff.json",
    "diff_checker": HERE / "describe_diff.py",
    "checker": HERE / "check_roundtrip.py",
    "runner_script": HERE / "run_native_ssh.ps1",
    "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
    "simlox_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
    "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
    "dictionary": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
    **{v: HERE / f"{v}-input.json" for v in RUNS},
}
REPORT = HERE / "review" / "independent-readonly-2026-10-01.json"
failures: list[str] = []
checks = 0


def check(label: str, good: bool) -> None:
    global checks
    checks += 1
    if not good:
        failures.append(label)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        out: list[str] = []
        quoted = escaped = False
        for i, char in enumerate(raw):
            if quoted:
                out.append(char)
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    quoted = False
            elif char == '"':
                quoted = True
                out.append(char)
            elif char == "," and raw[i + 1:].lstrip().startswith(("]", "}")):
                continue
            else:
                out.append(char)
        return json.loads("".join(out))


def tabmap(doc: dict) -> dict[str, dict]:
    items = doc["model"]["tables"]
    result = {t["name"]: t for t in items}
    check("unique model tables", len(items) == len(result))
    return result


def populated(doc: dict) -> dict[str, dict]:
    result = {}
    for name, table in tabmap(doc).items():
        rows = [row for instance in table["instances"] for row in instance["rows"]]
        for row in rows:
            check(f"{name} rectangular source/export", len(row) == len(table["columns"]))
        if rows:
            result[name] = {"columns": table["columns"], "rows": rows}
    return result


def field(table: dict, row: list, name: str):
    return row[[c["name"] for c in table["columns"]].index(name)]


def source_checks() -> None:
    for key, expected in FROZEN.items():
        check(f"frozen SHA {key}", FILES[key].is_file() and sha(FILES[key]) == expected)
    contract = read(FILES["contract"])
    diff = read(FILES["exact_diff"])
    parent = tabmap(read(PARENT))
    check("accepted parent signoff", (AIR / "A13-start-dependence-v1.0.0" /
          "cli-scope-signoff-2026-09-30.md").is_file())
    check("contract identity and limited gate", contract["case_id"] == "A13" and
          contract["variant_id"] == "A13.var04" and contract["case_version"] == "1.0.2-candidate" and
          contract["publication_state"] == "not_published" and
          any("#204" in line for line in contract["predeclared_native_gate"]) and
          any("no native event log" in line for line in contract["predeclared_native_gate"]))
    check("contract parent/source hashes", contract["parent"]["input_sha256"] == FROZEN["parent"] and
          contract["inputs_sha256"] == {v: FROZEN[v] for v in RUNS} and
          contract["exact_diff_sha256"] == FROZEN["exact_diff"] and
          contract["source"]["manual_sha256"] == FROZEN["manual"] and
          contract["source"]["dictionary_sha256"] == FROZEN["dictionary"])
    check("both prior diagnostics excluded", {d["package"] for d in contract["excluded_diagnostics"]} ==
          {"../A13-var04-unfinished-precedent-v1.0.0", "../A13-var04-unfinished-precedent-v1.0.1"})
    check("declared diff parent", diff["parent_sha256"] == FROZEN["parent"])
    child = {}
    for v in RUNS:
        check(f"{v} unchanged from v1.0.1 source", sha(FILES[v]) == sha(PRIOR / f"{v}-input.json"))
        t = tabmap(read(FILES[v]))
        child[v] = t
        check(f"{v} parent table inventory", parent.keys() == t.keys() and len(t) == 32)
        changes = {n: {"before": parent[n]["instances"], "after": t[n]["instances"]}
                   for n in parent if parent[n] != t[n]}
        expected = ({"ProblemDescription", "Control", "ResultCollection"} |
                    ({"MissionDependence"} if v == "unfinished-control" else set()))
        check(f"{v} exact source changed tables", set(changes) == expected and
              changes == diff["variants"][v]["changed_tables"] and
              sorted(set(parent) - set(changes)) == diff["variants"][v]["unchanged_tables"] and
              diff["variants"][v]["input_sha256"] == FROZEN[v])
        control = t["Control"]
        row = control["instances"][0]["rows"][0]
        check(f"{v} short stop and seed", all(field(control, row, n) == x for n, x in
              (("SIMPE", 11), ("RCEND", 11), ("RCINT", .5), ("RSEED", "1"))))
        result = t["ResultCollection"]
        rows = result["instances"][0]["rows"]
        check(f"{v} explicit 11-hour report window", len(rows) == 2 and
              {field(result, r, "RTYPE") for r in rows} == {"MISSION", "SYSTEM"} and
              all(field(result, r, "RCSTA") == 0 and field(result, r, "RCEND") == 11 and
                  field(result, r, "RCINT") == .5 for r in rows))
        system = t["System"]
        check(f"{v} no system failure rate", field(system, system["instances"][0]["rows"][0], "FRT") == 0)
        check(f"{v} populated table count", len(populated(read(FILES[v]))) ==
              (13 if v == "unfinished-control" else 14))
    check("pair differs only label and START row", [n for n in parent if
          child["unfinished-control"][n] != child["unfinished-dependency"][n]] ==
          ["ProblemDescription", "MissionDependence"])


def run_checks(v: str) -> dict:
    run = HERE / "runs" / RUNS[v]
    inv, closure, steps = (read(run / f) for f in ("invocation.json", "closure.json", "steps.json"))
    check(f"{v} invocation identity", inv["schema"].startswith("simlox-a13-var04-unfinished-precedent-v102-") and
          inv["case_id"] == "A13" and inv["variant_id"] == "A13.var04" and
          inv["case_version"] == "1.0.2-candidate" and inv["variant"] == v and
          inv["run_id"] == RUNS[v] and inv["input_sha256"] == FROZEN[v] and
          inv["parent_sha256"] == FROZEN["parent"] and inv["scope"] == "start_dependency_unfinished_precedent")
    check(f"{v} run location", Path(inv["original_run_dir"]).resolve() == run.resolve())
    check(f"{v} session0 SSH/mutex/GUI", inv["execution_mode"] == "ssh_cli_v1" and
          inv["session_id"] == 0 and inv["ssh_connection_present"] is True and
          "sshd.exe" in inv["ssh_ancestor_names"] and
          inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and
          inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1 and
          bool(inv["gui"]["start_utc"]))
    check(f"{v} closure identity", closure["schema"].startswith("simlox-a13-var04-unfinished-precedent-v102-") and
          closure["run_id"] == RUNS[v] and closure["invocation_sha256"] == sha(run / "invocation.json") and
          closure["error"] is None and closure["scope"] == "start_dependency_unfinished_precedent")
    expected = {k: FROZEN[k] for k in ("parent", "contract", "builder", "exact_diff", "diff_checker",
               "checker", "runner_script", "python", "simlox_exe")}
    expected["input"] = FROZEN[v]
    for key, value in expected.items():
        check(f"{v} frozen before/after {key}", inv["source_hashes_before"].get(key) == value and
              closure["source_hashes_before"].get(key) == value and
              closure["source_hashes_after"].get(key) == value)
    check(f"{v} invocation top-level hashes", inv["contract_sha256"] == expected["contract"] and
          inv["builder_sha256"] == expected["builder"] and inv["checker_sha256"] == expected["checker"] and
          inv["python_sha256"] == expected["python"] and
          inv["runner_script_sha256"] == expected["runner_script"] and
          inv["simlox_exe_sha256"] == expected["simlox_exe"])
    raw_names = {p.name for p in run.iterdir() if p.is_file()} - {"invocation.json", "closure.json"}
    check(f"{v} complete raw inventory", raw_names == set(closure["raw"]) and len(raw_names) == 9)
    for name, meta in closure["raw"].items():
        p = run / name
        check(f"{v} sealed {name}", p.stat().st_size == meta["bytes"] and sha(p) == meta["sha256"])
    check(f"{v} exactly four guarded steps", [s["name"] for s in steps] ==
          ["import", "export", "calc", "check_import_export"] and
          [s["status"] for s in steps] == ["completed", "completed", "calc_observed", "completed"] and
          all(s["exit_code"] == 0 and s["gui_preserved"] and s["error"] is None for s in steps))
    for i, s in enumerate(steps):
        start = datetime.fromisoformat(s["started_utc"].replace("Z", "+00:00"))
        end = datetime.fromisoformat(s["completed_utc"].replace("Z", "+00:00"))
        check(f"{v} step {i} time order", start <= end and
              (i == 0 or datetime.fromisoformat(steps[i-1]["completed_utc"].replace("Z", "+00:00")) <= start))
    check(f"{v} planned command identity", all(steps[i]["arguments"] ==
          inv["planned_commands"][i]["arguments"] for i in range(3)) and
          steps[3]["arguments"] == inv["planned_check"]["arguments"] and
          inv["planned_report"]["condition"] == "calc converter errors zero and SXO longer than four bytes")
    check(f"{v} copied source SHA", sha(run / "input.json") == FROZEN[v])
    before, after = populated(native(run / "input.json")), populated(native(run / "roundtrip-raw.json"))
    check(f"{v} populated source row count", len(before) == (13 if v == "unfinished-control" else 14))
    for name, table in before.items():
        check(f"{v} source roundtrip {name}", after.get(name) == table)
    check(f"{v} import/export markers", "Import completed!" in
          (run / "import.log").read_text(encoding="utf-8-sig", errors="replace") and
          "Export completed!" in (run / "export.log").read_text(encoding="utf-8-sig", errors="replace"))
    check(f"{v} author's roundtrip corroboration", read(run / "roundtrip-validation.json")["passed"] is True)
    log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    check(f"{v} exact Operations #204", len(re.findall(r"\(error #204\) Some missions may not return before simulation period ends", log)) == 1 and
          "Form: Operations\nrec 1: (error #204)" in log.replace("\r\n", "\n") and
          len(re.findall(r"\(error #", log)) == 1)
    check(f"{v} exact converter counts/warnings", "Input conversion completed. Errors: 1, Warnings: 2, Notes: 0" in log and
          len(re.findall(r"\(warning #108\)", log)) == 1 and
          len(re.findall(r"\(warning #126\)", log)) == 1 and
          len(re.findall(r"\(warning #", log)) == 2)
    check(f"{v} invalid four-byte SXO", (run / "model.sxo").stat().st_size == 4 and
          sha(run / "model.sxo") == "2a2d5e177502c5a794270deadd8dd755859f202a96d9d27568826ab0b69f984b")
    check(f"{v} no simulation/report outputs", all(not (run / name).exists() for name in
          ("model.log", "report-raw.json", "report-export.log")) and
          "Starting simulation..." not in log and "Saving results" not in log)
    return {"run_id": RUNS[v], "closure_sha256": sha(run / "closure.json"),
            "converter_errors": 1, "warning_codes": [108, 126], "sxo_bytes": 4,
            "source_populated_tables": len(before), "native_event_log": False, "native_report": False}


def main() -> int:
    source_checks()
    run_details = {v: run_checks(v) for v in RUNS}
    result = {"schema": "simlox-a13-unfinished-v102-independent-readonly/v1",
              "passed": not failures, "check_count": checks, "passed_count": checks - len(failures),
              "failures": failures,
              "decision": "GO_bounded_paired_Operations_204_converter_rejection" if not failures else "NO_GO",
              "scope": "two fixed hour-11 inputs differing only in one START row; converter-level rejection only",
              "limitations": ["No mission events, 22-bin report, terminal state, or unfinished-precedent runtime behavior exists in these runs",
                              "Reproduces one pre-observed negative pair; not a universal unfinished-mission rule",
                              "No GUI visual content, other schedule/failure/seed, or cross-engine claim"],
              "frozen_sha256": FROZEN, "runs": run_details}
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    print(json.dumps({k: result[k] for k in ("passed", "check_count", "passed_count", "decision", "failures")}, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
