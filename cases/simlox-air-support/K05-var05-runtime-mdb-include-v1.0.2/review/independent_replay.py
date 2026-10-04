"""Independent, read-only K05.var05 native evidence replay.

Reads the sealed MDB through 32-bit ODBC; never invokes SIMLOX or author code.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess


CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
RUN = CASE / "runs" / "k05-var05-mdb-v102-ssh-20261004-01"
PARENT = ROOT / "K02-var01-json-structure-v1.0.1"
PARENT_RUN = PARENT / "runs" / "k02-var01-named-v101-ssh-20261004-01"
RESULT = CASE / "review" / "independent-verdict.json"
PS32 = Path(r"C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe")

checks = 0
failures: list[str] = []


def check(ok: bool, label: str) -> None:
    global checks
    checks += 1
    if not ok:
        failures.append(label)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def native_json(path: Path):
    """Remove trailing commas outside strings in one linear scan."""
    raw = path.read_text(encoding="utf-8-sig")
    out = []
    quoted = False
    escaped = False
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
        elif char == ",":
            j = i + 1
            while j < len(raw) and raw[j].isspace():
                j += 1
            if j >= len(raw) or raw[j] not in "]}":
                out.append(char)
        else:
            out.append(char)
    return json.loads("".join(out))


def table(doc: dict, section: str, name: str) -> dict:
    matches = [t for t in doc[section]["tables"] if t["name"] == name]
    check(len(matches) == 1, f"one {section}.{name} table")
    return matches[0]


def populated(doc: dict) -> dict[str, dict]:
    return {t["name"]: t for t in doc["model"]["tables"] if any(
        any(v is not None for v in row)
        for inst in t.get("instances", []) for row in inst.get("rows", []))}


def odbc_inspection(mdb: Path) -> dict:
    # The installed x86 Access ODBC driver is queried separately from the
    # author helper. ReadOnly=1 and no SQL mutation; source hash checked after.
    code = r'''
$ErrorActionPreference='Stop'
$c=New-Object System.Data.Odbc.OdbcConnection("Driver={Microsoft Access Driver (*.mdb)};DBQ=$env:K05_REVIEW_MDB;ReadOnly=1;")
try {
  $c.Open()
  $names=@($c.GetSchema('Tables').Rows | Where-Object { $_['TABLE_TYPE'] -eq 'TABLE' } | ForEach-Object { [string]$_['TABLE_NAME'] } | Sort-Object)
  $cmd=$c.CreateCommand(); $cmd.CommandText='SELECT * FROM [Station]'
  $r=$cmd.ExecuteReader()
  try {
    $cols=@(); for($i=0;$i -lt $r.FieldCount;$i++) { $cols += [string]$r.GetName($i) }
    $rows=@(); while($r.Read()) { $values=@(); for($i=0;$i -lt $r.FieldCount;$i++) { $values += $r.GetValue($i) }; $rows += ,$values }
  } finally { $r.Close() }
  [pscustomobject]@{ tables=$names; columns=$cols; rows=$rows } | ConvertTo-Json -Depth 8 -Compress
} finally { $c.Close() }
'''
    env = dict(os.environ, K05_REVIEW_MDB=str(mdb))
    proc = subprocess.run(
        [str(PS32), "-NoProfile", "-NonInteractive", "-Command", code],
        text=True, encoding="utf-8", capture_output=True, env=env, timeout=30,
        check=False,
    )
    check(proc.returncode == 0, "read-only x86 ODBC query succeeds")
    if proc.returncode:
        failures.append(f"ODBC: {proc.stderr.strip()[:250]}")
        return {}
    return json.loads(proc.stdout)


def main() -> None:
    contract = native_json(CASE / "contract.json")
    invocation = native_json(RUN / "invocation.json")
    closure = native_json(RUN / "closure.json")
    steps = native_json(RUN / "steps.json")
    parent_closure = native_json(PARENT_RUN / "closure.json")
    source = native_json(CASE / "main-input.json")
    parent = native_json(PARENT / "named-input.json")
    database_source = native_json(CASE / "database-source.json")

    check(contract["run_id"] == RUN.name, "contract run ID")
    check(sha(CASE / "contract.json") == closure["source_hashes_before"]["contract.json"], "contract SHA sealed")
    check(sha(PARENT / "named-input.json") == contract["dependency"]["input_sha256"], "accepted K02 source pin")
    check(sha(PARENT_RUN / "closure.json") == contract["dependency"]["closure_sha256"], "accepted K02 closure pin")
    check(parent_closure["error"] is None, "accepted K02 closure succeeded")
    check(sha(CASE / "main-input.json") == contract["inputs_sha256"]["main"], "main source pin")
    check(sha(CASE / "database-source.json") == contract["inputs_sha256"]["database_source"], "MDB source pin")
    check(sha(RUN / "invocation.json") == closure["invocation_sha256"], "invocation SHA seal")
    check(invocation["source_hashes_before"] == closure["source_hashes_before"] == closure["source_hashes_after"], "before/after source map stable")
    source_paths = {
        "main_input": CASE / "main-input.json",
        "database_source": CASE / "database-source.json",
        "accepted_parent": PARENT / "named-input.json",
        "accepted_parent_closure": PARENT_RUN / "closure.json",
        "exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
        "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
        "build.py": CASE / "build.py",
        "create_mdb_x86.ps1": CASE / "create_mdb_x86.ps1",
        "run_native_ssh.ps1": CASE / "run_native_ssh.ps1",
        "contract.json": CASE / "contract.json",
        "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
        "powershell_x86": PS32,
    }
    for key, path in source_paths.items():
        check(path.is_file() and sha(path) == closure["source_hashes_before"].get(key), f"frozen source {key}")
    check(closure["error"] is None and closure["run_id"] == RUN.name, "native closure success and identity")
    check(len(closure["raw"]) == 14, "14 sealed raw files")
    for name, record in sorted(closure["raw"].items()):
        file = RUN / name
        check(file.is_file() and file.stat().st_size == record["bytes"] and sha(file) == record["sha256"], f"raw SHA and size {name}")

    check(invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0, "SSH session zero")
    check("sshd.exe" in invocation["ssh_ancestor_names"], "recorded sshd ancestry")
    check(invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", "global native queue")
    check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, "recorded GUI identity")
    check([s["name"] for s in steps] == ["database_create", "main_import", "main_export", "calc", "jsonreport"], "five guarded steps")
    for step in steps:
        check(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"] is True, f"step {step['name']}")
    original = "mdb=Microsoft Access Driver (*.mdb)|"
    temporary = "mdb=Microsoft Access Driver (*.mdb, *.accdb)|"
    check(invocation["database_association_before"] == original, "recorded registry original")
    check(invocation["database_association_during_calc"] == temporary, "recorded temporary calc mapping")
    check(closure["database_association_after"] == original, "recorded registry restored")
    runner = (CASE / "run_native_ssh.ps1").read_text(encoding="utf-8-sig")
    check("finally" in runner and "Set-ItemProperty" in runner and "Get-ItemPropertyValue" in runner, "sealed runner restore path")

    parent_tables = populated(parent)
    main_tables = populated(source)
    check(set(main_tables) == set(parent_tables) | {"IncludeFiles"}, "only one new populated table")
    for name in sorted(parent_tables.keys() - {"Station"}):
        check(main_tables[name] == parent_tables[name], f"unchanged K02 table {name}")
    old_station = table(parent, "model", "Station")
    new_station = table(source, "model", "Station")
    check(old_station["columns"] == new_station["columns"], "Station schema unchanged")
    check(len(old_station["instances"]) == 2 and len(new_station["instances"]) == 1, "BASE row split from main")
    check(new_station["instances"][0] == old_station["instances"][1], "AUX named instance retained")
    check(old_station["instances"][0]["rows"][0][:4] == ["BASE-01", "Teaching base", 1, "WS"], "parent BASE row")
    included = table(source, "model", "IncludeFiles")
    check(len(included["instances"]) == 1 and len(included["instances"][0]["rows"]) == 1, "one IncludeFiles row")
    check(included["instances"][0]["rows"][0][0] == str(RUN / "included.mdb"), "absolute sealed MDB path")
    check(database_source == {"table": "Station", "columns": ["STID", "DESCR", "QTY", "TYPE"], "rows": [["BASE-01", "Teaching base", 1, "WS"]]}, "one-row MDB source")

    mdb_hash_before = sha(RUN / "included.mdb")
    inspected = odbc_inspection(RUN / "included.mdb")
    check(inspected.get("tables") == ["Station"], "independent MDB user-table enumeration")
    check(inspected.get("columns") == ["STID", "DESCR", "QTY", "TYPE"], "independent MDB columns")
    check(inspected.get("rows") == [["BASE-01", "Teaching base", 1, "WS"]], "independent MDB physical row")
    check(sha(RUN / "included.mdb") == mdb_hash_before == closure["raw"]["included.mdb"]["sha256"], "MDB unchanged by read-only inspection")
    native_readback = native_json(RUN / "included.readback.json")
    check(native_readback["process_bitness"] == 32 and native_readback["driver"] == "Microsoft Access Driver (*.mdb)", "sealed helper x86 readback provenance")
    check(native_readback["database_sha256"] == mdb_hash_before and native_readback["database_bytes"] == (RUN / "included.mdb").stat().st_size, "sealed helper MDB identity")
    check(native_readback["rows"] == [{"STID": "BASE-01", "DESCR": "Teaching base", "QTY": 1, "TYPE": "WS"}], "helper row matches independent MDB query")

    exported = native_json(RUN / "main-roundtrip-raw.json")
    for name, authored in sorted(main_tables.items()):
        observed = table(exported, "model", name)
        source_columns = [c["name"] for c in authored["columns"]]
        exported_columns = [c["name"] for c in observed["columns"]]
        check(all(c in exported_columns for c in source_columns), f"roundtrip columns {name}")
        projection = [exported_columns.index(c) for c in source_columns]
        for inst in authored["instances"]:
            matching = [x for x in observed["instances"] if x["instance_name"] == inst["instance_name"]]
            check(len(matching) == 1, f"roundtrip instance {name}/{inst['instance_name']}")
            if matching:
                actual_rows = [[row[i] for i in projection] for row in matching[0]["rows"]]
                check(actual_rows == inst["rows"], f"roundtrip rows {name}/{inst['instance_name']}")
    check((RUN / "main-input.json").read_bytes() == (CASE / "main-input.json").read_bytes(), "main run copy exact")
    check((RUN / "database-source.json").read_bytes() == (CASE / "database-source.json").read_bytes(), "MDB source run copy exact")

    runlog = (RUN / "run.log").read_text(encoding="utf-8-sig")
    check("Including data from file:" in runlog and "included.mdb" in runlog, "native include opened")
    check("Station, 1 record inserted" in runlog and "Data successfully included" in runlog, "native one-row merge")
    check("Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in runlog, "converter zero errors")
    check(set(re.findall(r"warning #(\d+)", runlog)) == {"108", "126"}, "converter warning set")
    check((RUN / "model.sxo").stat().st_size > 4, "usable SXO")
    check((RUN / "model.log").read_bytes() == (PARENT_RUN / "model.log").read_bytes(), "parent event-log byte parity")
    check((RUN / "report-raw.json").read_bytes() == (PARENT_RUN / "report-raw.json").read_bytes(), "parent report byte parity")
    events = (RUN / "model.log").read_text(encoding="utf-8-sig")
    for event in ["Time: 7 <TEACH-UNIT> mission ordered: BASIC-MISSION", "Time: 8 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting", "Time: 11 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success", "Time: 11 <TEACH-AIR-01,BASE-01,0> System ready"]:
        check(event in events, f"event {event[:45]}")
    report = native_json(RUN / "report-raw.json")
    counts = {}
    for name in ["SystemResults", "StockTotalResults"]:
        t = table(report, "report", name)
        rows = [row for inst in t["instances"] for row in inst["rows"]]
        counts[name] = len(rows)
        check(len(rows) == 72, f"72 {name} half-hour rows")
    check(len(table(report, "report", "ResultSummary")["instances"][0]["rows"]) == 1, "one summary row")
    check("systems ready: 1" in events.split("Time: 24")[0], "physical ready state restored")

    verdict = {
        "schema": "independent-readonly-review/v1",
        "case": "K05.var05 v1.0.2",
        "run_id": RUN.name,
        "verdict": "GO — bounded runtime MDB IncludeFiles one-row Station merge" if not failures else "NO-GO",
        "passed": not failures,
        "checks_passed": checks - len(failures),
        "checks_total": checks,
        "failures": failures,
        "evidence": {
            "closure_sha256": sha(RUN / "closure.json"),
            "mdb_sha256": sha(RUN / "included.mdb"),
            "model_log_sha256": sha(RUN / "model.log"),
            "report_sha256": sha(RUN / "report-raw.json"),
            "independent_odbc": inspected,
            "report_rows": counts,
        },
        "limits": [
            "One frozen installed-CLI run and one absolute task-local MDB include; no relative, nested, invalid, multiple-table, or cross-engine behavior established.",
            "The registry before/during/after values are sealed runner observations and restore-path code; this replay did not independently snapshot the historical registry state.",
            "The native log proves a Station row was inserted, while the independent 32-bit ODBC read verifies the sealed MDB has exactly one user TABLE and the expected row. Jet system tables are excluded from that count.",
            "Event/report byte parity demonstrates this one model's behavior; it does not prove general equivalence of MDB and JSON source semantics.",
        ],
    }
    RESULT.write_text(json.dumps(verdict, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{verdict['verdict']}: {verdict['checks_passed']}/{checks}; {RESULT}")


if __name__ == "__main__":
    main()
