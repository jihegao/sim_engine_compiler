"""Independent, read-only replay of the sealed A01.var01 zero-return evidence.

This checker does not import or execute the author validator or SIMLOX.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
RUN_ID = "a01-var01-tfret0-v010-ssh-20261006-01"
RUN = CASE / "runs" / RUN_ID
PARENT = ROOT / "A01-single-aircraft-single-mission"
RAW_ROOT = Path("C:/Users/user/Documents/Codex/2026-09-27/simlox-case-library-a01-a02-v1/repo/data/local/simlox-case-library/v1/A01")
FINAL = RAW_ROOT / "a01-bound-final-20260927-03"
REPLAY = RAW_ROOT / "a01-bound-replay-20260927-04"
SIBLING = ROOT / "A01-var01-zero-outbound-v0.1.0"
SIBLING_RUN = SIBLING / "runs/a01-var01-tfout0-v010-ssh-20261006-01"
SIBLING2 = ROOT / "A01-var01-sum-one-v0.1.0"
SIBLING2_RUN = SIBLING2 / "runs/a01-var01-sum1-v010-ssh-20261006-01"
MANUAL = Path("C:/Program Files/Systecon/SIMLOX/UserDoc/SIMLOX.pdf")
EXE = Path("C:/Program Files/Systecon/SIMLOX/Simlox.exe")
PYTHON = Path("C:/Users/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe")
EXPECTED_CLOSURE = "4700b79d6209fc6213810cfa11760687e0fa3e294e2dc4f31532ca1f2fdc8517"
EXPECTED_SOURCE = {
    "child_input": CASE / "native-input.json",
    "child_contract": CASE / "contract.json",
    "contract_review": CASE / "review/independent-contract-go-2026-10-06.md",
    "negative_checker": CASE / "check_negative_control.py",
    "negative_control": CASE / "review/negative-control-accepted-parent.json",
    "builder": CASE / "build.py",
    "parent_diff": CASE / "check_parent_diff.py",
    "roundtrip_checker": CASE / "check_roundtrip.py",
    "behavior_validator": CASE / "validate_native_cli.py",
    "runner_script": CASE / "run_native_ssh.ps1",
    "accepted_input": PARENT / "native-input.json",
    "accepted_contract": PARENT / "contract.json",
    "accepted_signoff": PARENT / "cli-scope-signoff-2026-09-29.md",
    "accepted_index": PARENT / "evidence-index.json",
    "accepted_final_closure": FINAL / "closure.json",
    "accepted_replay_closure": REPLAY / "closure.json",
    "sibling_input": SIBLING / "native-input.json",
    "sibling_signoff": SIBLING / "cli-scope-signoff-2026-10-06.md",
    "sibling_index": SIBLING / "evidence-index.json",
    "sibling_closure": SIBLING_RUN / "closure.json",
    "sibling2_input": SIBLING2 / "native-input.json",
    "sibling2_signoff": SIBLING2 / "cli-scope-signoff-2026-10-06.md",
    "sibling2_index": SIBLING2 / "evidence-index.json",
    "sibling2_closure": SIBLING2_RUN / "closure.json",
    "installed_manual": MANUAL,
    "installed_exe": EXE,
    "python": PYTHON,
    "prelaunch_approval": CASE / "review/independent-prelaunch-go.json",
}
EXPECTED_RAW = {
    "input.json", "model.sxi", "import.log", "roundtrip-raw.json", "export.log",
    "roundtrip-validation.json", "model.sxo", "run.log", "model.log",
    "report-raw.json", "report-export.log", "steps.json",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def json_doc(path: Path, allow_trailing_commas: bool = False):
    data = path.read_bytes().decode("utf-8-sig")
    if allow_trailing_commas:
        # Remove separator commas only outside quoted strings; leave raw bytes untouched.
        out = []
        quoted = escaped = False
        for pos, char in enumerate(data):
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
            elif char == "," and re.match(r"\s*[}\]]", data[pos + 1 :]):
                continue
            else:
                out.append(char)
        data = "".join(out)
    return json.loads(data)


def authored_cells(doc):
    cells = {}
    tables = {}
    for tab in doc["model"]["tables"]:
        name = tab["name"]
        assert name not in tables, name
        tables[name] = tab
        fields = [c["name"] for c in tab["columns"]]
        for ii, instance in enumerate(tab["instances"]):
            for ri, row in enumerate(instance["rows"]):
                assert len(row) == len(fields), (name, ii, ri)
                for field, value in zip(fields, row):
                    key = (name, ii, ri, field)
                    assert key not in cells, key
                    cells[key] = value
    return cells, tables


def report_table(doc, name):
    matches = [t for t in doc["report"]["tables"] if t["name"] == name]
    assert len(matches) == 1, name
    tab = matches[0]
    columns = [c["name"] for c in tab["columns"]]
    assert len(columns) == len(set(columns)), name
    rows = [r for instance in tab["instances"] for r in instance["rows"]]
    assert all(len(r) == len(columns) for r in rows), name
    return columns, rows


def log_lines(path):
    return [line.strip() for line in path.read_text(encoding="utf-8-sig").splitlines()]


def times(lines, text):
    found = []
    for line in lines:
        if text in line:
            match = re.match(r"Time:\s*([0-9]+(?:\.[0-9]+)?)\s", line)
            assert match, line
            found.append((float(match.group(1)), line))
    return found


def replay():
    count, failures = 0, []

    def ck(label, actual, expected):
        nonlocal count
        count += 1
        if actual != expected:
            failures.append({"check": label, "actual": actual, "expected": expected})

    ck("child closure SHA", sha(RUN / "closure.json"), EXPECTED_CLOSURE)
    closure = json_doc(RUN / "closure.json")
    invocation = json_doc(RUN / "invocation.json")
    ck("closure and invocation run IDs", (closure["run_id"], invocation["run_id"]), (RUN_ID, RUN_ID))
    ck("closure error", closure["error"], None)
    ck("closure invocation SHA", closure["invocation_sha256"], sha(RUN / "invocation.json"))
    ck("invocation input SHA", invocation["input_sha256"], sha(CASE / "native-input.json"))
    ck("invocation contract SHA", invocation["contract_sha256"], sha(CASE / "contract.json"))
    ck("invocation runner SHA", invocation["runner_script_sha256"], sha(CASE / "run_native_ssh.ps1"))
    ck("source stability", closure["source_hashes_before"], closure["source_hashes_after"])
    ck("invocation source map", invocation["source_hashes_before"], closure["source_hashes_before"])
    ck("source map keys", set(closure["source_hashes_before"]), set(EXPECTED_SOURCE))
    for key, path in EXPECTED_SOURCE.items():
        ck("source pin " + key, closure["source_hashes_before"].get(key), sha(path))
    ck("approved run", json_doc(EXPECTED_SOURCE["prelaunch_approval"])["decision"], "GO_PRELAUNCH")

    index = json_doc(PARENT / "evidence-index.json")
    ck("accepted run IDs", {x["run_id"] for x in index["runs"]}, {FINAL.name, REPLAY.name})
    nparent = 0
    for entry in index["runs"]:
        for name, pin in entry["artifacts"].items():
            path = Path(pin["path"])
            ck(f"parent seal {entry['run_id']}/{name}", (path.stat().st_size, sha(path)), (pin["bytes"], pin["sha256"]))
            nparent += 1
    ck("parent raw count", nparent, 34)
    sibling_closure = json_doc(SIBLING_RUN / "closure.json")
    ck("sibling closure run", sibling_closure["run_id"], SIBLING_RUN.name)
    ck("sibling closure error", sibling_closure["error"], None)
    ck("sibling raw count", len(sibling_closure["raw"]), 12)
    for name, pin in sibling_closure["raw"].items():
        path = SIBLING_RUN / name
        ck("sibling seal " + name, (path.stat().st_size, sha(path)), (pin["bytes"], pin["sha256"]))
    sibling2_closure = json_doc(SIBLING2_RUN / "closure.json")
    ck("second sibling closure run", sibling2_closure["run_id"], SIBLING2_RUN.name)
    ck("second sibling closure error", sibling2_closure["error"], None)
    ck("second sibling raw count", len(sibling2_closure["raw"]), 12)
    for name, pin in sibling2_closure["raw"].items():
        path = SIBLING2_RUN / name
        ck("second sibling seal " + name, (path.stat().st_size, sha(path)), (pin["bytes"], pin["sha256"]))

    ck("child raw name set", set(closure["raw"]), EXPECTED_RAW)
    ck("child directory raw set", {p.name for p in RUN.iterdir() if p.is_file()} - {"closure.json", "invocation.json"}, EXPECTED_RAW)
    ck("no failure seal", (RUN / "failure-seal.json").exists(), False)
    for name, pin in closure["raw"].items():
        path = RUN / name
        ck("child seal " + name, (path.stat().st_size, sha(path)), (pin["bytes"], pin["sha256"]))

    ck("SSH0 and sshd ancestry", (invocation["session_id"], invocation["ssh_connection_present"], "sshd.exe" in invocation["ssh_ancestor_names"]), (0, True, True))
    ck("host mutex", invocation["queue_mutex"], "Global\\SimloxIssue18NativeQueue")
    gui = invocation["gui"]
    ck("protected GUI", (gui["pid"], gui["session_id"], gui["start_unix_ms"]), (13340, 1, 1790590196826))
    steps = json_doc(RUN / "steps.json")
    ck("five ordered guarded steps", [(s["name"], s["status"], s["exit_code"], s["gui_preserved"]) for s in steps],
       [(s, "completed", 0, True) for s in ("import", "export", "check_import_export", "calc", "jsonreport")])
    ck("four planned native commands", [s["name"] for s in invocation["planned_commands"]], ["import", "export", "calc", "jsonreport"])
    ck("roundtrip precedes calc", steps[2]["completed_utc"] < steps[3]["started_utc"], True)

    parent_cells, _ = authored_cells(json_doc(PARENT / "native-input.json"))
    child_cells, child_tables = authored_cells(json_doc(CASE / "native-input.json"))
    ck("155 source cell keys", (len(parent_cells), set(child_cells)), (155, set(parent_cells)))
    for key in parent_cells:
        expected = 0.0 if key == ("MissionType", 0, 0, "TFRET") else parent_cells[key]
        ck("source cell " + str(key), child_cells[key], expected)
    ck("return fraction zero", child_cells[("MissionType", 0, 0, "TFRET")], 0.0)
    ck("outbound fraction retained", child_cells[("MissionType", 0, 0, "TFOUT")], 0.25)
    ck("copied input byte identity", sha(RUN / "input.json"), sha(CASE / "native-input.json"))
    exported_cells, exported_tables = authored_cells(json_doc(RUN / "roundtrip-raw.json", True))
    authored_names = {name for name, tab in child_tables.items() if any(i["rows"] for i in tab["instances"])}
    ck("13 authored row-containing tables", len(authored_names), 13)
    for name in authored_names:
        ck("roundtrip table " + name, (exported_tables[name]["columns"], exported_tables[name]["instances"]),
           (child_tables[name]["columns"], child_tables[name]["instances"]))
    ck("roundtrip validation result", json_doc(RUN / "roundtrip-validation.json")["passed"], True)
    ck("import completion", "Import completed!" in (RUN / "import.log").read_text(encoding="utf-8-sig"), True)
    ck("export completion", "Export completed!" in (RUN / "export.log").read_text(encoding="utf-8-sig"), True)

    calc = (RUN / "run.log").read_text(encoding="utf-8-sig")
    ck("converter summary", re.findall(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", calc), [("0", "2", "0")])
    ck("converter warning codes", re.findall(r"\(warning #(\d+)\)", calc), ["108", "126"])
    ck("converter error codes", re.findall(r"\(error #(\d+)\)", calc), [])
    ck("nonempty simulation output", (RUN / "model.sxo").stat().st_size > 4, True)
    ck("nonempty report", (RUN / "report-raw.json").stat().st_size > 4, True)

    old_lines, new_lines = log_lines(FINAL / "model.log"), log_lines(RUN / "model.log")
    token = "task starting: <TEACH-AIR-01,0>"
    ck("parent task start", [x[0] for x in times(old_lines, token)], [8.5])
    ck("child task start", [x[0] for x in times(new_lines, token)], [8.5])
    ck("child task start mission identity", len(times(new_lines, token)) == 1 and "<BASIC-MISSION,TEACH-UNIT,0,0,0>" in times(new_lines, token)[0][1], True)
    completion_token = "task completed: <TEACH-AIR-01,0>"
    ck("parent task completion", [x[0] for x in times(old_lines, completion_token)], [9.5])
    ck("child task completion", [x[0] for x in times(new_lines, completion_token)], [10.0])
    ck("same-time task completion and mission success", [x[0] for x in times(new_lines, completion_token) + times(new_lines, "mission success:")], [10.0, 10.0])
    ck("one physical mission start", [x[0] for x in times(new_lines, "mission starting, duration: 2 : <TEACH-AIR-01,0>")], [8.0])
    ck("one mission success", [x[0] for x in times(new_lines, "mission success:")], [10.0])
    ck("one mission completion", [x[0] for x in times(new_lines, "mission completed: <TEACH-AIR-01,0>")], [10.0])
    ck("same aircraft arrival", [x[0] for x in times(new_lines, "System arrives <TEACH-AIR-01,0>")], [10.0])
    ck("same aircraft ready", [x[0] for x in times(new_lines, "System ready <TEACH-AIR-01,0>")], [10.0, 10.0])
    ck("pre-h8 event prefix", [x for x in new_lines if x.startswith("Time:") and float(x.split()[1]) < 8],
       [x for x in old_lines if x.startswith("Time:") and float(x.split()[1]) < 8])
    ck("all other event lines", [x for x in new_lines if completion_token not in x], [x for x in old_lines if completion_token not in x])
    ck("no failed or cancelled mission", any("mission aborted:" in x or "mission cancelled:" in x for x in new_lines), False)

    ck("raw report byte parity with parent", sha(RUN / "report-raw.json"), sha(FINAL / "report-raw.json"))
    ck("raw report byte parity with zero-outbound sibling", sha(RUN / "report-raw.json"), sha(SIBLING_RUN / "report-raw.json"))
    ck("raw report byte parity with sum-one sibling", sha(RUN / "report-raw.json"), sha(SIBLING2_RUN / "report-raw.json"))
    old_report, new_report = json_doc(FINAL / "report-raw.json", True), json_doc(RUN / "report-raw.json", True)
    ck("report table names", {t["name"] for t in new_report["report"]["tables"]},
       {"ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults"})
    for name, expected_shape in (("SystemResults", (72, 40)), ("StockTotalResults", (72, 16)), ("ResultSummary", (1, 11))):
        old_columns, old_rows = report_table(old_report, name)
        new_columns, new_rows = report_table(new_report, name)
        ck(name + " schema", (len(new_rows), len(new_columns), new_columns), (expected_shape[0], expected_shape[1], old_columns))
        ck(name + " parent shape", (len(old_rows), len(old_columns)), expected_shape)
        for ri, (old_row, new_row) in enumerate(zip(old_rows, new_rows)):
            for ci, field in enumerate(new_columns):
                ck(f"{name}[{ri}].{field}", new_row[ci], old_row[ci])
        if name != "ResultSummary":
            start, end = new_columns.index("STINT"), new_columns.index("ETINT")
            for ri, row in enumerate(new_rows):
                ck(f"{name} interval {ri}", (row[start], row[end]), (ri / 2, (ri + 1) / 2))
        if name == "SystemResults":
            col = {field: ci for ci, field in enumerate(new_columns)}
            integral = lambda field: sum((row[col[field]] or 0) * 0.5 for row in new_rows)
            ck("ready aircraft-hours", integral("NSYRY"), 33.0)
            ck("available aircraft-hours", integral("NSYA"), 36.0)
            ck("mission flight hours", integral("FTMO"), 2.0)
            ck("terminal ready and available", (new_rows[-1][col["NSYRY"]], new_rows[-1][col["NSYA"]]), (1, 1))
            for field in ("NFAIL", "NREPT", "NPMT", "NPMS"):
                ck(field + " all zero", all(row[col[field]] in (0, None) for row in new_rows), True)

    verdict = {
        "schema": "simlox-a01-var01-zero-return-v010-independent-replay/v1",
        "decision": "GO_BOUNDED" if not failures else "NO_GO",
        "run_id": RUN_ID,
        "checks": count,
        "failures": failures,
        "child_closure_sha256": EXPECTED_CLOSURE,
        "parent_raw_seals": nparent,
        "sibling_raw_seals": len(sibling_closure["raw"]),
        "second_sibling_raw_seals": len(sibling2_closure["raw"]),
        "child_raw_seals": len(closure["raw"]),
        "scope": "one fixed h8-10 mission and sole TFRET 0.25 to 0 with TFOUT 0.25; h10 task completion and full report parity",
        "limits": ["No general schedule/duration or travel-geography rule", "No GUI visual or full A01.var01 claim", "Raw default report parsed from a normalized in-memory copy only"],
    }
    return verdict


if __name__ == "__main__":
    result = replay()
    data = (json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")
    path = CASE / "review/independent-verdict.json"
    path.write_bytes(data)
    print(json.dumps({"decision": result["decision"], "checks": result["checks"], "failures": len(result["failures"]), "verdict_sha256": hashlib.sha256(data).hexdigest()}))
    raise SystemExit(0 if result["decision"] == "GO_BOUNDED" else 1)
