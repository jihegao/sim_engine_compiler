"""Independent read-only replay of K05.var02 ODBC null-merge evidence."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import winreg


CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
RUN = CASE / "runs" / "k05-var02-odbc-null-v101-ssh-20261004-01"
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


def load(path: Path):
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
            out.append(char)
            string = True
        elif char == ",":
            next_index = index + 1
            while next_index < len(raw) and raw[next_index].isspace():
                next_index += 1
            if next_index == len(raw) or raw[next_index] not in "]}":
                out.append(char)
        else:
            out.append(char)
    return json.loads("".join(out))


def table(doc: dict, section: str, name: str) -> dict:
    matches = [entry for entry in doc[section]["tables"] if entry["name"] == name]
    check(len(matches) == 1, f"one {section} table {name}")
    return matches[0]


def populated(doc: dict) -> dict[str, dict]:
    return {entry["name"]: entry for entry in doc["model"]["tables"]
            if any(any(value is not None for value in row)
                   for instance in entry.get("instances", [])
                   for row in instance.get("rows", []))}


def inspect_mdb(path: Path) -> dict:
    code = r'''
$ErrorActionPreference='Stop'
$c=New-Object System.Data.Odbc.OdbcConnection("Driver={Microsoft Access Driver (*.mdb)};DBQ=$env:K05_REVIEW_MDB;ReadOnly=1;")
try {
  $c.Open()
  $names=@($c.GetSchema('Tables').Rows | Where-Object { $_['TABLE_TYPE'] -eq 'TABLE' } | ForEach-Object { [string]$_['TABLE_NAME'] } | Sort-Object)
  $cmd=$c.CreateCommand(); $cmd.CommandText='SELECT * FROM [Station]'
  $r=$cmd.ExecuteReader()
  try {
    $columns=@(); for($i=0;$i -lt $r.FieldCount;$i++) { $columns += [string]$r.GetName($i) }
    $rows=@(); while($r.Read()) { $values=@(); for($i=0;$i -lt $r.FieldCount;$i++) { $values += $r.GetValue($i) }; $rows += ,$values }
  } finally { $r.Close() }
  [pscustomobject]@{tables=$names;columns=$columns;rows=$rows} | ConvertTo-Json -Depth 8 -Compress
} finally { $c.Close() }
'''
    env = dict(os.environ, K05_REVIEW_MDB=str(path))
    result = subprocess.run([str(PS32), "-NoProfile", "-NonInteractive", "-Command", code],
                            text=True, encoding="utf-8", capture_output=True,
                            env=env, timeout=30, check=False)
    check(result.returncode == 0, "independent read-only x86 MDB query")
    if result.returncode:
        failures.append(f"ODBC query: {result.stderr.strip()[:250]}")
        return {}
    return json.loads(result.stdout)


def has_current_dsn(name: str) -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, rf"Software\ODBC\ODBC.INI\{name}"):
            return True
    except FileNotFoundError:
        return False


def main() -> None:
    contract = load(CASE / "contract.json")
    invocation = load(RUN / "invocation.json")
    closure = load(RUN / "closure.json")
    steps = load(RUN / "steps.json")
    outcome = load(RUN / "outcome.json")
    dsn_record = load(RUN / "dsn-observation.json")
    parent_closure = load(PARENT_RUN / "closure.json")
    named_parent = load(PARENT / "named-input.json")
    baseline = load(CASE / "baseline-input.json")
    mdb_source = load(CASE / "database-source.json")

    check(contract["run_id"] == RUN.name == invocation["run_id"] == closure["run_id"], "frozen run identity")
    parent_paths = {
        "named_input_sha256": PARENT / "named-input.json",
        "native_sxi_sha256": PARENT_RUN / "model.sxi",
        "native_roundtrip_sha256": PARENT_RUN / "roundtrip-raw.json",
        "closure_sha256": PARENT_RUN / "closure.json",
        "signoff_sha256": PARENT / "cli-scope-signoff-2026-10-04.md",
    }
    for field, path in parent_paths.items():
        check(path.is_file() and sha(path) == contract["dependency"][field], f"accepted K02 {field}")
    check(parent_closure["error"] is None, "accepted K02 closure success")
    check(sha(CASE / "baseline-input.json") == contract["inputs_sha256"]["baseline_input"], "baseline source pin")
    check(sha(CASE / "database-source.json") == contract["inputs_sha256"]["database_source"], "MDB source pin")
    check(sha(RUN / "invocation.json") == closure["invocation_sha256"], "invocation seal")
    check(invocation["source_hashes_before"] == closure["source_hashes_before"] == closure["source_hashes_after"], "before/after source stability")
    sources = {
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
        "powershell_x86": PS32,
    }
    for name, path in sources.items():
        check(path.is_file() and sha(path) == closure["source_hashes_before"].get(name), f"source SHA {name}")
    check(closure["error"] is None and outcome["error"] is None, "closure and outcome no audit errors")
    check(len(closure["raw"]) == 26, "26 sealed raw files")
    for name, seal in sorted(closure["raw"].items()):
        path = RUN / name
        check(path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"], f"raw SHA and size {name}")
    for name in ("baseline-input.json", "database-source.json"):
        check((CASE / name).read_bytes() == (RUN / name).read_bytes(), f"source run copy {name}")

    check(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"], "session-zero SSH provenance")
    check(invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", "host mutex")
    check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, "protected GUI identity")
    check([step["name"] for step in steps] == ["baseline_import", "baseline_export", "baseline_calc", "baseline_jsonreport", "database_create", "odbc_import", "merged_export", "calc", "jsonreport"], "nine guarded steps")
    for step in steps:
        check(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"] is True, f"step {step['name']}")
    original = "mdb=Microsoft Access Driver (*.mdb)|"
    check(invocation["association_before"] == closure["association_after"] == original, "recorded MDB association unchanged")
    check(invocation["dsn_before"] == closure["dsn_after"] == "absent", "recorded temporary DSN absence before/after")
    check(invocation["dsn_name"] == contract["user_dsn"] and invocation["dsn_driver"] == "Microsoft Access Driver (*.mdb, *.accdb)", "frozen DSN identity")
    check(outcome["dsn_removed_before_calc"] is True and all(outcome[key] == "completed" for key in ("baseline", "import_export", "calc", "report")), "recorded DSN removal before calc")
    check(not has_current_dsn(contract["user_dsn"]), "review-time user DSN absent")
    runner = (CASE / "run_native_ssh.ps1").read_text(encoding="utf-8-sig")
    check("Remove-OwnedDsn" in runner and "finally" in runner and "Add-OdbcDsn" in runner, "sealed runner temporary DSN cleanup path")
    check(dsn_record["name"] == contract["user_dsn"] and dsn_record["platform"] == "64-bit" and dsn_record["type"] == "User" and dsn_record["database_path"] == str(RUN / "input.mdb"), "sealed temporary DSN record")

    parent_tables = populated(named_parent)
    baseline_tables = populated(baseline)
    check(set(parent_tables) == set(baseline_tables) and len(baseline_tables) == 10, "same 10 K02 row-containing tables")
    for name in sorted(parent_tables.keys() - {"Station"}):
        check(parent_tables[name] == baseline_tables[name], f"unchanged K02 business table {name}")
    old_station = table(named_parent, "model", "Station")
    baseline_station = table(baseline, "model", "Station")
    check(old_station["columns"] == baseline_station["columns"], "Station schema unchanged")
    check([row for inst in old_station["instances"] for row in inst["rows"]] == baseline_station["instances"][0]["rows"], "same two K02 Station business rows")
    check(len(baseline_station["instances"]) == 1 and baseline_station["instances"][0]["instance_name"] == "", "one default Station instance")

    mdb_hash = sha(RUN / "input.mdb")
    physical = inspect_mdb(RUN / "input.mdb")
    check(physical.get("tables") == ["Station"], "MDB sole user Station table")
    check(physical.get("columns") == mdb_source["columns"], "MDB physical columns")
    check(physical.get("rows") == mdb_source["rows"] == [["BASE-01", "ODBC merged teaching base", None, None]], "MDB physical row has true QTY/TYPE nulls")
    check(sha(RUN / "input.mdb") == mdb_hash == closure["raw"]["input.mdb"]["sha256"], "MDB unchanged by independent read-only query")
    readback = load(RUN / "input.readback.json")
    check(readback["database_sha256"] == mdb_hash and readback["process_bitness"] == 32 and readback["rows"] == physical["rows"], "sealed x86 helper readback agrees")
    check(dsn_record["database_sha256"] == mdb_hash and dsn_record["select_row"] == physical["rows"][0], "sealed 64-bit DSN observation agrees")

    imported = (RUN / "import.log").read_text(encoding="utf-8-sig")
    check(f"Importing data from {contract['user_dsn']}" in imported and "Station, 1 record updated" in imported and "Data successfully imported" in imported, "native ODBC update, not insertion")
    base_export = load(RUN / "base-roundtrip-raw.json")
    merged_export = load(RUN / "roundtrip-raw.json")
    for name, authored in sorted(baseline_tables.items()):
        for phase, export in (("base", base_export), ("merged", merged_export)):
            actual = table(export, "model", name)
            columns = [entry["name"] for entry in authored["columns"]]
            actual_columns = [entry["name"] for entry in actual["columns"]]
            check(all(column in actual_columns for column in columns), f"{phase} columns {name}")
            indices = [actual_columns.index(column) for column in columns]
            for instance in authored["instances"]:
                matches = [item for item in actual["instances"] if item["instance_name"] == instance["instance_name"]]
                check(len(matches) == 1, f"{phase} instance {name}/{instance['instance_name']}")
                if matches:
                    rows = [[row[index] for index in indices] for row in matches[0]["rows"]]
                    if phase == "merged" and name == "Station":
                        expected = [row.copy() for row in instance["rows"]]
                        expected[0][1] = "ODBC merged teaching base"
                    else:
                        expected = instance["rows"]
                    check(rows == expected, f"{phase} exact business rows {name}/{instance['instance_name']}")
    base_station = table(base_export, "model", "Station")
    merged_station = table(merged_export, "model", "Station")
    check(len(base_station["instances"]) == len(merged_station["instances"]) == 1, "no extra Station instance")
    check(len(base_station["instances"][0]["rows"]) == len(merged_station["instances"][0]["rows"]) == 2, "no duplicate BASE-01 row")
    base_cols = [entry["name"] for entry in base_station["columns"]]
    merged_cols = [entry["name"] for entry in merged_station["columns"]]
    check(base_cols == merged_cols, "native Station schema stable")
    before = base_station["instances"][0]["rows"]
    after = merged_station["instances"][0]["rows"]
    differences = [(row_index, base_cols[index], old, new) for row_index, (old_row, new_row) in enumerate(zip(before, after)) for index, (old, new) in enumerate(zip(old_row, new_row)) if old != new]
    check(differences == [(0, "DESCR", "Teaching base", "ODBC merged teaching base")], "native Station-only DESCR delta")
    check(after[0][base_cols.index("QTY")] == 1 and after[0][base_cols.index("TYPE")] == "WS", "null QTY/TYPE preserved existing values")

    for phase, log_name, sxo_name in (("base", "base-run.log", "base.sxo"), ("merged", "run.log", "model.sxo")):
        text = (RUN / log_name).read_text(encoding="utf-8-sig")
        check("Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in text, f"{phase} zero converter errors")
        check(re.findall(r"\(warning #(\d+)\)", text) == ["108", "126"], f"{phase} reviewed warning set")
        check((RUN / sxo_name).stat().st_size > 4, f"{phase} valid SXO")
    for name in ("base.log", "model.log"):
        check((RUN / name).read_bytes() == (PARENT_RUN / "model.log").read_bytes(), f"{name} accepted K02 event parity")
    for name in ("base-report-raw.json", "report-raw.json"):
        check((RUN / name).read_bytes() == (PARENT_RUN / "report-raw.json").read_bytes(), f"{name} accepted K02 report parity")
    check((RUN / "base.log").read_bytes() == (RUN / "model.log").read_bytes(), "baseline/merged event parity")
    check((RUN / "base-report-raw.json").read_bytes() == (RUN / "report-raw.json").read_bytes(), "baseline/merged report parity")
    report = load(RUN / "report-raw.json")
    report_rows = {}
    for name in ("SystemResults", "StockTotalResults"):
        entry = table(report, "report", name)
        report_rows[name] = sum(len(instance["rows"]) for instance in entry["instances"])
        check(report_rows[name] == 72, f"72 {name} bins")

    verdict = {
        "schema": "independent-readonly-review/v1",
        "case": "K05.var02 v1.0.1",
        "run_id": RUN.name,
        "passed": not failures,
        "verdict": "GO — bounded default-Station ODBC key update with null non-erasure" if not failures else "NO-GO",
        "checks_passed": checks - len(failures),
        "checks_total": checks,
        "failures": failures,
        "evidence": {
            "closure_sha256": sha(RUN / "closure.json"),
            "mdb_sha256": sha(RUN / "input.mdb"),
            "independent_odbc": physical,
            "station_cell_delta": differences,
            "model_log_sha256": sha(RUN / "model.log"),
            "report_sha256": sha(RUN / "report-raw.json"),
            "report_rows": report_rows,
            "review_time_user_dsn_absent": not has_current_dsn(contract["user_dsn"]),
        },
        "limits": [
            "One matched BASE-01 key in a single default Station instance, one task-local MDB, and one installed Access ODBC driver. Named-instance merging and general null/key rules are not established.",
            "The earlier v1.0.0 named-instance #2013 diagnostic is excluded and does not support this positive merge claim.",
            "Temporary DSN creation/removal and GUI preservation are sealed runner observations; the reviewer additionally checked only current DSN absence, not historical host state.",
            "Event/report equality supports this one teaching model's unchanged outcome; no ODBC report-output or cross-engine claim is made.",
        ],
    }
    RESULT.write_text(json.dumps(verdict, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{verdict['verdict']}: {verdict['checks_passed']}/{checks}")


if __name__ == "__main__":
    main()
