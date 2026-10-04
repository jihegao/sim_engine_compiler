"""Independent, read-only K04.var01 nested MDB include evidence replay."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess


CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
RUN = CASE / "runs" / "k04-var01-nested-mdb-v100-ssh-20261004-01"
PARENT = ROOT / "K05-var05-runtime-mdb-include-v1.0.2"
PARENT_RUN = PARENT / "runs" / "k05-var05-mdb-v102-ssh-20261004-01"
RESULT = CASE / "review" / "independent-verdict.json"
PS32 = Path(r"C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe")
total = 0
failures: list[str] = []


def check(condition: bool, label: str) -> None:
    global total
    total += 1
    if not condition:
        failures.append(label)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path):
    """Read native JSON, tolerating trailing commas without quadratic rescans."""
    raw = path.read_text(encoding="utf-8-sig")
    out = []
    string = escape = False
    for index, char in enumerate(raw):
        if string:
            out.append(char)
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                string = False
        elif char == '"':
            string = True
            out.append(char)
        elif char == ",":
            next_index = index + 1
            while next_index < len(raw) and raw[next_index].isspace():
                next_index += 1
            if next_index >= len(raw) or raw[next_index] not in "]}":
                out.append(char)
        else:
            out.append(char)
    return json.loads("".join(out))


def get_table(document: dict, section: str, name: str) -> dict:
    found = [entry for entry in document[section]["tables"] if entry["name"] == name]
    check(len(found) == 1, f"unique {section} table {name}")
    return found[0]


def populated(document: dict) -> dict[str, dict]:
    return {
        entry["name"]: entry for entry in document["model"]["tables"]
        if any(any(value is not None for value in row)
               for instance in entry.get("instances", [])
               for row in instance.get("rows", []))
    }


def inspect_mdb(path: Path, table_name: str) -> dict:
    # Independent 32-bit ODBC schema enumeration and SELECT. No author helper,
    # no SIMLOX, no registry change; ReadOnly=1. Hash is checked afterward.
    code = r'''
$ErrorActionPreference='Stop'
$c=New-Object System.Data.Odbc.OdbcConnection("Driver={Microsoft Access Driver (*.mdb)};DBQ=$env:K04_REVIEW_MDB;ReadOnly=1;")
try {
  $c.Open()
  $tables=@($c.GetSchema('Tables').Rows | Where-Object { $_['TABLE_TYPE'] -eq 'TABLE' } | ForEach-Object { [string]$_['TABLE_NAME'] } | Sort-Object)
  $cmd=$c.CreateCommand(); $cmd.CommandText='SELECT * FROM ['+$env:K04_REVIEW_TABLE+']'
  $reader=$cmd.ExecuteReader()
  try {
    $columns=@(); for($i=0;$i -lt $reader.FieldCount;$i++) { $columns += [string]$reader.GetName($i) }
    $rows=@(); while($reader.Read()) { $values=@(); for($i=0;$i -lt $reader.FieldCount;$i++) { $values += $reader.GetValue($i) }; $rows += ,$values }
  } finally { $reader.Close() }
  [pscustomobject]@{tables=$tables;columns=$columns;rows=$rows} | ConvertTo-Json -Depth 8 -Compress
} finally { $c.Close() }
'''
    env = dict(os.environ, K04_REVIEW_MDB=str(path), K04_REVIEW_TABLE=table_name)
    process = subprocess.run(
        [str(PS32), "-NoProfile", "-NonInteractive", "-Command", code],
        capture_output=True, text=True, encoding="utf-8", env=env, timeout=30,
        check=False,
    )
    check(process.returncode == 0, f"read-only x86 ODBC query {table_name}")
    if process.returncode:
        failures.append(f"ODBC {table_name}: {process.stderr.strip()[:250]}")
        return {}
    return json.loads(process.stdout)


def main() -> None:
    contract = load(CASE / "contract.json")
    source = load(CASE / "main-input.json")
    level1_source = load(CASE / "level1-source.json")
    level2_source = load(CASE / "level2-source.json")
    parent_source = load(PARENT / "main-input.json")
    invocation = load(RUN / "invocation.json")
    closure = load(RUN / "closure.json")
    steps = load(RUN / "steps.json")
    parent_closure = load(PARENT_RUN / "closure.json")

    check(contract["run_id"] == RUN.name and closure["run_id"] == RUN.name, "frozen run ID")
    check(sha(PARENT / "main-input.json") == contract["dependency"]["input_sha256"], "K05 accepted source SHA")
    check(sha(PARENT_RUN / "closure.json") == contract["dependency"]["closure_sha256"], "K05 accepted closure SHA")
    check(sha(PARENT / "cli-scope-signoff-2026-10-04.md") == contract["dependency"]["signoff_sha256"], "K05 accepted signoff SHA")
    check(parent_closure["error"] is None, "K05 parent successful")
    for name, filename in [("main", "main-input.json"), ("level1_source", "level1-source.json"), ("level2_source", "level2-source.json")]:
        check(sha(CASE / filename) == contract["inputs_sha256"][name], f"contract input {name}")
    check(sha(RUN / "invocation.json") == closure["invocation_sha256"], "sealed invocation")
    check(invocation["source_hashes_before"] == closure["source_hashes_before"] == closure["source_hashes_after"], "source map stable before/after")
    source_paths = {
        "main_input": CASE / "main-input.json",
        "level1_source": CASE / "level1-source.json",
        "level2_source": CASE / "level2-source.json",
        "contract": CASE / "contract.json",
        "accepted_parent": PARENT / "main-input.json",
        "accepted_parent_db_source": PARENT / "database-source.json",
        "accepted_parent_closure": PARENT_RUN / "closure.json",
        "accepted_parent_signoff": PARENT / "cli-scope-signoff-2026-10-04.md",
        "exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
        "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
        "build.py": CASE / "build.py",
        "create_level1_mdb_x86.ps1": CASE / "create_level1_mdb_x86.ps1",
        "create_level2_mdb_x86.ps1": CASE / "create_level2_mdb_x86.ps1",
        "run_native_ssh.ps1": CASE / "run_native_ssh.ps1",
        "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
        "powershell_x86": PS32,
    }
    for name, path in source_paths.items():
        check(path.is_file() and sha(path) == closure["source_hashes_before"].get(name), f"source SHA {name}")
    check(closure["error"] is None, "native closure no error")
    check(len(closure["raw"]) == 17, "17 sealed raw files")
    for name, record in sorted(closure["raw"].items()):
        file = RUN / name
        check(file.is_file() and file.stat().st_size == record["bytes"] and sha(file) == record["sha256"], f"raw seal {name}")

    check(invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0, "SSH session zero")
    check("sshd.exe" in invocation["ssh_ancestor_names"], "recorded sshd ancestor")
    check(invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", "global queue")
    check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, "recorded GUI identity")
    check([s["name"] for s in steps] == ["level2_create", "level1_create", "main_import", "main_export", "calc", "jsonreport"], "six guarded steps")
    for step in steps:
        check(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"] is True, f"step {step['name']}")
    original = "mdb=Microsoft Access Driver (*.mdb)|"
    temporary = "mdb=Microsoft Access Driver (*.mdb, *.accdb)|"
    check(invocation["database_association_before"] == original, "registry mapping before")
    check(invocation["database_association_during_calc"] == temporary, "temporary mapping during calc")
    check(closure["database_association_after"] == original, "recorded registry restoration")
    runner = (CASE / "run_native_ssh.ps1").read_text(encoding="utf-8-sig")
    check("finally" in runner and "Set-ItemProperty" in runner and "Get-ItemPropertyValue" in runner, "sealed runner restoration code")

    parent_tables = populated(parent_source)
    child_tables = populated(source)
    check(set(child_tables) == set(parent_tables), "same populated main tables")
    for name in sorted(parent_tables.keys() - {"IncludeFiles"}):
        check(child_tables[name] == parent_tables[name], f"unchanged main table {name}")
    old_include = get_table(parent_source, "model", "IncludeFiles")
    new_include = get_table(source, "model", "IncludeFiles")
    check(old_include["columns"] == new_include["columns"], "main IncludeFiles schema unchanged")
    check(len(old_include["instances"]) == len(new_include["instances"]) == 1 and len(old_include["instances"][0]["rows"]) == len(new_include["instances"][0]["rows"]) == 1, "sole main IncludeFiles row")
    old_row = old_include["instances"][0]["rows"][0]
    new_row = new_include["instances"][0]["rows"][0]
    check(new_row == [str(RUN / "level1.mdb"), "Nested support organization", None] and old_row[1:] == ["Required base station", None], "main IncludeFiles path and description delta")
    check(level1_source == {"table": "IncludeFiles", "columns": ["INCFN", "INCCO", "NOTE"], "rows": [[str(RUN / "level2.mdb"), "Required base station", None]]}, "level1 source points only to level2")
    check(level2_source == {"table": "Station", "columns": ["STID", "DESCR", "QTY", "TYPE"], "rows": [["BASE-01", "Teaching base", 1, "WS"]]}, "level2 source contains K02 base")

    mdb_before = {level: sha(RUN / f"{level}.mdb") for level in ("level1", "level2")}
    level1 = inspect_mdb(RUN / "level1.mdb", "IncludeFiles")
    level2 = inspect_mdb(RUN / "level2.mdb", "Station")
    check(level1.get("tables") == ["IncludeFiles"], "level1 exactly one user table")
    check(level1.get("columns") == ["INCFN", "INCCO", "NOTE"], "level1 physical schema")
    check(level1.get("rows") == [[str(RUN / "level2.mdb"), "Required base station", None]], "level1 physical nested path")
    check(level2.get("tables") == ["Station"], "level2 exactly one user table")
    check(level2.get("columns") == ["STID", "DESCR", "QTY", "TYPE"], "level2 physical schema")
    check(level2.get("rows") == [["BASE-01", "Teaching base", 1, "WS"]], "level2 physical base row")
    for level, observed in [("level1", level1), ("level2", level2)]:
        check(sha(RUN / f"{level}.mdb") == mdb_before[level] == closure["raw"][f"{level}.mdb"]["sha256"], f"{level} MDB unchanged by query")
        readback = load(RUN / f"{level}.readback.json")
        check(readback["process_bitness"] == 32 and readback["database_sha256"] == mdb_before[level], f"{level} sealed helper readback identity")

    exported = load(RUN / "main-roundtrip-raw.json")
    for name, authored in sorted(child_tables.items()):
        actual = get_table(exported, "model", name)
        source_names = [column["name"] for column in authored["columns"]]
        actual_names = [column["name"] for column in actual["columns"]]
        check(all(column in actual_names for column in source_names), f"roundtrip columns {name}")
        indexes = [actual_names.index(column) for column in source_names]
        for instance in authored["instances"]:
            matches = [x for x in actual["instances"] if x["instance_name"] == instance["instance_name"]]
            check(len(matches) == 1, f"roundtrip instance {name}/{instance['instance_name']}")
            if matches:
                check([[row[index] for index in indexes] for row in matches[0]["rows"]] == instance["rows"], f"roundtrip rows {name}/{instance['instance_name']}")
    for name in ("main-input.json", "level1-source.json", "level2-source.json"):
        check((RUN / name).read_bytes() == (CASE / name).read_bytes(), f"run source copy {name}")

    runlog = (RUN / "run.log").read_text(encoding="utf-8-sig")
    first = runlog.find("Including data from file:")
    second = runlog.find("Including data from file:", first + 1)
    check(first >= 0 and second > first and runlog.count("Including data from file:") == 2, "native traverses two include files in order")
    check("level1.mdb" in runlog[first:second] and "level2.mdb" in runlog[second:], "native level1 then level2 identities")
    check("IncludeFiles, 1 record inserted" in runlog[first:second], "native nested IncludeFiles inserted")
    check("Station, 1 record inserted" in runlog[second:], "native Station inserted")
    check(runlog.count("Data successfully included") == 2, "both native includes succeed")
    check("Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in runlog, "zero converter errors")
    check(set(re.findall(r"warning #(\d+)", runlog)) == {"108", "126"}, "reviewed warning codes")
    check((RUN / "model.sxo").stat().st_size > 4, "usable SXO")
    check((RUN / "model.log").read_bytes() == (PARENT_RUN / "model.log").read_bytes(), "K05 event-log byte parity")
    check((RUN / "report-raw.json").read_bytes() == (PARENT_RUN / "report-raw.json").read_bytes(), "K05 report byte parity")
    events = (RUN / "model.log").read_text(encoding="utf-8-sig")
    for marker in ("Time: 7 <TEACH-UNIT> mission ordered: BASIC-MISSION", "Time: 8 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting", "Time: 11 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success", "Time: 11 <TEACH-AIR-01,BASE-01,0> System ready"):
        check(marker in events, f"teaching event {marker[:45]}")
    report = load(RUN / "report-raw.json")
    counts = {}
    for name in ("SystemResults", "StockTotalResults"):
        entry = get_table(report, "report", name)
        counts[name] = sum(len(instance["rows"]) for instance in entry["instances"])
        check(counts[name] == 72, f"72 {name} bins")
    check(len(get_table(report, "report", "ResultSummary")["instances"][0]["rows"]) == 1, "one result summary")

    result = {
        "schema": "independent-readonly-review/v1",
        "case": "K04.var01 v1.0.0",
        "run_id": RUN.name,
        "passed": not failures,
        "verdict": "GO — bounded two-level MDB IncludeFiles traversal" if not failures else "NO-GO",
        "checks_passed": total - len(failures),
        "checks_total": total,
        "failures": failures,
        "evidence": {
            "closure_sha256": sha(RUN / "closure.json"),
            "level1_mdb_sha256": sha(RUN / "level1.mdb"),
            "level2_mdb_sha256": sha(RUN / "level2.mdb"),
            "independent_odbc": {"level1": level1, "level2": level2},
            "model_log_sha256": sha(RUN / "model.log"),
            "report_sha256": sha(RUN / "report-raw.json"),
            "report_rows": counts,
        },
        "limits": [
            "One fixed two-level absolute-path MDB chain under this installed CLI; no nested SXI/OPI, relative-path, conflict, invalid-file, or cross-engine rule established.",
            "The native converter log explicitly records traversal and insertion; the MDB queries independently verify one user table and one row in each sealed file, excluding Access system tables.",
            "Registry restoration and GUI preservation are sealed runner observations; this review did not independently observe their historical state.",
            "Byte parity to accepted K05 proves this teaching model's output, not universal semantic equivalence of nested and flat includes.",
        ],
    }
    RESULT.write_text(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{result['verdict']}: {result['checks_passed']}/{total}")


if __name__ == "__main__":
    main()
