"""Independent, read-only replay of K04.var04 conflict diagnostics."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess


CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
RUN = CASE / "runs" / "k04-var04-duplicate-control-key-v100-ssh-20261004-01"
PARENT = ROOT / "K04-var01-nested-mdb-include-v1.0.0"
PARENT_RUN = PARENT / "runs" / "k04-var01-nested-mdb-v100-ssh-20261004-01"
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
    quoted = escaped = False
    for pos, char in enumerate(raw):
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
            next_pos = pos + 1
            while next_pos < len(raw) and raw[next_pos].isspace():
                next_pos += 1
            if next_pos == len(raw) or raw[next_pos] not in "]}":
                out.append(char)
        else:
            out.append(char)
    return json.loads("".join(out))


def table(doc: dict, name: str) -> dict:
    found = [entry for entry in doc["model"]["tables"] if entry["name"] == name]
    check(len(found) == 1, f"one model table {name}")
    return found[0]


def populated(doc: dict) -> dict[str, dict]:
    return {entry["name"]: entry for entry in doc["model"]["tables"]
            if any(any(value is not None for value in row)
                   for instance in entry.get("instances", [])
                   for row in instance.get("rows", []))}


def inspect_mdb(path: Path) -> dict:
    # Separate from author readback: x86 ODBC enumerates user TABLEs and reads
    # every row. ReadOnly=1. MDB hash is checked after closing the connection.
    code = r'''
$ErrorActionPreference='Stop'
$c=New-Object System.Data.Odbc.OdbcConnection("Driver={Microsoft Access Driver (*.mdb)};DBQ=$env:K04_REVIEW_MDB;ReadOnly=1;")
try {
  $c.Open()
  $names=@($c.GetSchema('Tables').Rows | Where-Object { $_['TABLE_TYPE'] -eq 'TABLE' } | ForEach-Object { [string]$_['TABLE_NAME'] } | Sort-Object)
  $contents=@{}
  foreach($name in $names) {
    $cmd=$c.CreateCommand(); $cmd.CommandText='SELECT * FROM ['+$name+']'
    $reader=$cmd.ExecuteReader()
    try {
      $columns=@(); for($i=0;$i -lt $reader.FieldCount;$i++) { $columns += [string]$reader.GetName($i) }
      $rows=@(); while($reader.Read()) { $values=@(); for($i=0;$i -lt $reader.FieldCount;$i++) { $values += $reader.GetValue($i) }; $rows += ,$values }
      $contents[$name]=[pscustomobject]@{columns=$columns;rows=$rows}
    } finally { $reader.Close() }
  }
  [pscustomobject]@{tables=$names;contents=$contents} | ConvertTo-Json -Depth 12 -Compress
} finally { $c.Close() }
'''
    env = dict(os.environ, K04_REVIEW_MDB=str(path))
    process = subprocess.run([str(PS32), "-NoProfile", "-NonInteractive", "-Command", code],
                             capture_output=True, text=True, encoding="utf-8", env=env,
                             timeout=30, check=False)
    check(process.returncode == 0, f"read-only MDB query {path.name}")
    if process.returncode:
        failures.append(f"ODBC {path.name}: {process.stderr.strip()[:250]}")
        return {}
    return json.loads(process.stdout)


def main() -> None:
    contract = load(CASE / "contract.json")
    invocation = load(RUN / "invocation.json")
    closure = load(RUN / "closure.json")
    steps = load(RUN / "steps.json")
    outcomes = load(RUN / "outcomes.json")
    parent_closure = load(PARENT_RUN / "closure.json")
    parent_source = load(PARENT / "main-input.json")
    source = {arm: load(CASE / f"{arm}-main-input.json") for arm in ("control", "key")}

    check(contract["run_id"] == RUN.name == invocation["run_id"] == closure["run_id"] == outcomes["run_id"], "run identity")
    parent_pins = {
        "main_input_sha256": PARENT / "main-input.json",
        "level2_station_source_sha256": PARENT / "level2-source.json",
        "closure_sha256": PARENT_RUN / "closure.json",
        "signoff_sha256": PARENT / "cli-scope-signoff-2026-10-04.md",
    }
    for key, path in parent_pins.items():
        check(sha(path) == contract["dependency"][key], f"accepted parent {key}")
    check(parent_closure["error"] is None, "parent closure succeeded")
    input_files = {
        "control_main": "control-main-input.json",
        "key_main": "key-main-input.json",
        "control_mdb_source": "control-mdb-source.json",
        "key_level1_source": "key-level1-source.json",
        "key_level2_source": "key-level2-source.json",
    }
    for key, filename in input_files.items():
        check(sha(CASE / filename) == contract["inputs_sha256"][key], f"contract input {key}")
    check(sha(RUN / "invocation.json") == closure["invocation_sha256"], "invocation seal")
    check(invocation["source_hashes_before"] == closure["source_hashes_before"] == closure["source_hashes_after"], "source hash stability")
    source_paths = {
        "contract": CASE / "contract.json",
        **{key: CASE / filename for key, filename in input_files.items()},
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
        "powershell_x86": PS32,
    }
    for name, path in source_paths.items():
        check(path.is_file() and sha(path) == closure["source_hashes_before"].get(name), f"source SHA {name}")
    check(closure["error"] is None and outcomes["error"] is None, "sealed diagnostic run no audit error")
    check(len(closure["raw"]) == 25, "25 sealed raw files")
    for name, record in sorted(closure["raw"].items()):
        path = RUN / name
        check(path.is_file() and path.stat().st_size == record["bytes"] and sha(path) == record["sha256"], f"raw seal {name}")
    for filename in input_files.values():
        check((RUN / filename).read_bytes() == (CASE / filename).read_bytes(), f"input run copy {filename}")

    check(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"], "session-zero SSH provenance")
    check(invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", "host mutex")
    check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, "protected GUI identity")
    check(invocation["association_before"] == closure["association_after"] == "mdb=Microsoft Access Driver (*.mdb)|", "recorded association restoration")
    check(invocation["association_during_calc"] == "mdb=Microsoft Access Driver (*.mdb, *.accdb)|", "temporary MDB association")
    check([step["name"] for step in steps] == ["create_control", "create_key_level2", "create_key_level1", "control_import", "control_export", "control_calc", "key_import", "key_export", "key_calc"], "nine guarded steps")
    for step in steps:
        check(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"] is True, f"step {step['name']}")

    parent_tables = populated(parent_source)
    for arm in ("control", "key"):
        tables = populated(source[arm])
        check(set(tables) == set(parent_tables) and len(tables) == 11, f"{arm} same 11 populated tables")
        for name in sorted(parent_tables.keys() - {"IncludeFiles"}):
            check(tables[name] == parent_tables[name], f"{arm} unchanged {name}")
        included = table(source[arm], "IncludeFiles")
        check(len(included["instances"]) == 1 and len(included["instances"][0]["rows"]) == 1, f"{arm} sole main include row")
        path = RUN / ("control.mdb" if arm == "control" else "key-level1.mdb")
        check(included["instances"][0]["rows"][0][0] == str(path), f"{arm} main MDB path")
        check(included["instances"][0]["rows"][0][1:] == (["Duplicate Control MDB probe", None] if arm == "control" else ["Duplicate Station key MDB probe", None]), f"{arm} exact include comment")
        exported = load(RUN / f"{arm}-roundtrip-raw.json")
        for name, authored in sorted(tables.items()):
            actual = table(exported, name)
            columns = [entry["name"] for entry in authored["columns"]]
            actual_columns = [entry["name"] for entry in actual["columns"]]
            check(all(column in actual_columns for column in columns), f"{arm} roundtrip columns {name}")
            projection = [actual_columns.index(column) for column in columns]
            for instance in authored["instances"]:
                matches = [item for item in actual["instances"] if item["instance_name"] == instance["instance_name"]]
                check(len(matches) == 1, f"{arm} roundtrip instance {name}/{instance['instance_name']}")
                if matches:
                    check([[row[index] for index in projection] for row in matches[0]["rows"]] == instance["rows"], f"{arm} roundtrip rows {name}/{instance['instance_name']}")

    mdb_spec = {
        "control": "control-mdb-source.json",
        "key-level1": "key-level1-source.json",
        "key-level2": "key-level2-source.json",
    }
    observations = {}
    for name, filename in mdb_spec.items():
        mdb = RUN / f"{name}.mdb"
        before = sha(mdb)
        observed = inspect_mdb(mdb)
        observations[name] = observed
        authored = load(CASE / filename)["tables"]
        check(observed.get("tables") == sorted(entry["table"] for entry in authored), f"{name} exact user table set")
        for entry in authored:
            found = observed.get("contents", {}).get(entry["table"], {})
            check(found.get("columns") == entry["columns"], f"{name} {entry['table']} columns")
            check(found.get("rows") == entry["rows"], f"{name} {entry['table']} rows")
        check(sha(mdb) == before == closure["raw"][f"{name}.mdb"]["sha256"], f"{name} read-only query did not change MDB")
        readback = load(RUN / f"{name}.readback.json")
        check(readback["database_sha256"] == before and readback["database_bytes"] == mdb.stat().st_size and readback["process_bitness"] == 32, f"{name} sealed helper readback identity")

    check(load(CASE / "control-mdb-source.json")["tables"][0]["table"] == "Control", "complete duplicate Control source table")
    control_mdb_row = load(CASE / "control-mdb-source.json")["tables"][0]
    main_control = table(source["control"], "Control")
    check(control_mdb_row["columns"] == [column["name"] for column in main_control["columns"]] and control_mdb_row["rows"] == main_control["instances"][0]["rows"], "included Control row exactly duplicates main Control")
    check(load(CASE / "key-level1-source.json")["tables"][1]["rows"][0][0] == load(CASE / "key-level2-source.json")["tables"][0]["rows"][0][0] == "BASE-01", "same Station key in two included files")
    check(load(CASE / "key-level1-source.json")["tables"][0]["rows"][0][0] == str(RUN / "key-level2.mdb"), "nested second MDB path")

    arm_results = {}
    for arm, expected_code, expected_warnings, expected_text in [
        ("control", "2043", ["108", "108", "126"], "Table already defined: Control"),
        ("key", "2013", ["108", "126"], "Double definition of data for: BASE-01"),
    ]:
        runlog = (RUN / f"{arm}-run.log").read_text(encoding="utf-8-sig", errors="replace")
        error_codes = re.findall(r"\(error #(\d+)\)", runlog)
        warning_codes = re.findall(r"\(warning #(\d+)\)", runlog)
        check(error_codes == [expected_code], f"{arm} only native error #{expected_code}")
        check(warning_codes == expected_warnings, f"{arm} exact warnings")
        check(expected_text in runlog, f"{arm} attributed error text")
        check(f"Input conversion completed. Errors: 1, Warnings: {len(expected_warnings)}, Notes: 0" in runlog, f"{arm} converter summary")
        check("Data successfully included" in runlog and "record inserted" in runlog, f"{arm} MDB actually traversed")
        if arm == "control":
            check("Control, 1 record inserted" in runlog and "Station, 1 record inserted" in runlog, "control MDB row insertions")
        else:
            check(runlog.count("Including data from file:") == 2 and runlog.count("Station, 1 record inserted") == 2, "two nested Station inserts")
        check((RUN / f"{arm}.sxo").stat().st_size == 4, f"{arm} unusable four-byte SXO")
        check(not (RUN / f"{arm}-model.log").exists() and not (RUN / f"{arm}-report-raw.json").exists(), f"{arm} no simulation/report")
        check(sha(RUN / f"{arm}.sxi") == outcomes["arms"][arm]["sxi_sha256"], f"{arm} SXI outcome SHA")
        check(sha(RUN / f"{arm}-run.log") == outcomes["arms"][arm]["run_log_sha256"], f"{arm} log outcome SHA")
        check(outcomes["arms"][arm]["converter_error_codes"] == [expected_code] and outcomes["arms"][arm]["converter_warning_codes"] == expected_warnings, f"{arm} outcome classification matches raw")
        arm_results[arm] = {"error_codes": error_codes, "warning_codes": warning_codes, "sxo_bytes": (RUN / f"{arm}.sxo").stat().st_size}

    result = {
        "schema": "independent-readonly-review/v1",
        "case": "K04.var04 v1.0.0",
        "run_id": RUN.name,
        "passed": not failures,
        "verdict": "GO — bounded duplicate-Control #2043 and repeated-Station-key #2013 converter rejections" if not failures else "NO-GO",
        "checks_passed": checks - len(failures),
        "checks_total": checks,
        "failures": failures,
        "evidence": {"closure_sha256": sha(RUN / "closure.json"), "raw_file_count": len(closure["raw"]), "arms": arm_results, "independent_odbc": observations},
        "limits": [
            "These are two isolated zero-simulation converter rejections from one frozen installed CLI run; neither arm produced a valid report.",
            "The #2043 Control case used one full additional Control row; the #2013 Station case repeated BASE-01 across two MDB include levels. Other table, key, field, and conflict precedence behavior is untested.",
            "Both logs contain reviewed #108/#126 warnings; the duplicate-Control log has #108 twice. Corrupted incidental File-path text in native run.log does not change the exact form/record error attribution.",
            "GUI and registry preservation are sealed runner observations, not independent historical host snapshots.",
        ],
    }
    RESULT.write_text(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{result['verdict']}: {result['checks_passed']}/{checks}")


if __name__ == "__main__":
    main()
