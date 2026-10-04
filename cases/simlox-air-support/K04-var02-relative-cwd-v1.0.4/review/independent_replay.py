"""Read-only independent replay of K04.var02 relative-CWD native evidence."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess


CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
RUN = CASE / "runs" / "k04-var02-relative-cwd-v104-ssh-20261004-01"
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


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def parse(path: Path):
    """Read SIMLOX JSON with a linear trailing-comma cleanup outside strings."""
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
            out.append(char)
            quoted = True
        elif char == ",":
            next_pos = pos + 1
            while next_pos < len(raw) and raw[next_pos].isspace():
                next_pos += 1
            if next_pos == len(raw) or raw[next_pos] not in "]}":
                out.append(char)
        else:
            out.append(char)
    return json.loads("".join(out))


def table(doc: dict, section: str, name: str) -> dict:
    matches = [entry for entry in doc[section]["tables"] if entry["name"] == name]
    check(len(matches) == 1, f"unique {section} {name}")
    return matches[0]


def populated(doc: dict) -> dict[str, dict]:
    return {
        entry["name"]: entry for entry in doc["model"]["tables"]
        if any(any(value is not None for value in row)
               for instance in entry.get("instances", [])
               for row in instance.get("rows", []))
    }


def mdb_query(path: Path, name: str) -> dict:
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
    env = dict(os.environ, K04_REVIEW_MDB=str(path), K04_REVIEW_TABLE=name)
    result = subprocess.run(
        [str(PS32), "-NoProfile", "-NonInteractive", "-Command", code],
        text=True, encoding="utf-8", capture_output=True, timeout=30, env=env,
        check=False,
    )
    check(result.returncode == 0, f"read-only ODBC {name}")
    if result.returncode:
        failures.append(f"ODBC {name}: {result.stderr.strip()[:250]}")
        return {}
    return json.loads(result.stdout)


def main() -> None:
    contract = parse(CASE / "contract.json")
    main_input = parse(CASE / "main-input.json")
    level1_source = parse(CASE / "level1-source.json")
    level2_source = parse(CASE / "level2-source.json")
    parent_input = parse(PARENT / "main-input.json")
    invocation = parse(RUN / "invocation.json")
    closure = parse(RUN / "closure.json")
    steps = parse(RUN / "steps.json")
    parent_closure = parse(PARENT_RUN / "closure.json")

    check(contract["run_id"] == RUN.name == invocation["run_id"] == closure["run_id"], "frozen run identity")
    for field, path in [
        ("main_input_sha256", PARENT / "main-input.json"),
        ("level1_source_sha256", PARENT / "level1-source.json"),
        ("level2_source_sha256", PARENT / "level2-source.json"),
        ("closure_sha256", PARENT_RUN / "closure.json"),
        ("signoff_sha256", PARENT / "cli-scope-signoff-2026-10-04.md"),
    ]:
        check(digest(path) == contract["dependency"][field], f"accepted parent pin {field}")
    check(parent_closure["error"] is None, "accepted parent closure success")
    for field, path in [("main", CASE / "main-input.json"), ("level1_source", CASE / "level1-source.json"), ("level2_source", CASE / "level2-source.json")]:
        check(digest(path) == contract["inputs_sha256"][field], f"contract source {field}")
    check(digest(RUN / "invocation.json") == closure["invocation_sha256"], "invocation seal")
    check(invocation["source_hashes_before"] == closure["source_hashes_before"] == closure["source_hashes_after"], "source stability")
    paths = {
        "main_input": CASE / "main-input.json",
        "level1_source": CASE / "level1-source.json",
        "level2_source": CASE / "level2-source.json",
        "contract": CASE / "contract.json",
        "accepted_parent_main": PARENT / "main-input.json",
        "accepted_parent_level1": PARENT / "level1-source.json",
        "accepted_parent_level2": PARENT / "level2-source.json",
        "accepted_parent_closure": PARENT_RUN / "closure.json",
        "accepted_parent_signoff": PARENT / "cli-scope-signoff-2026-10-04.md",
        "level1_generator": PARENT / "create_level1_mdb_x86.ps1",
        "level2_generator": PARENT / "create_level2_mdb_x86.ps1",
        "exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
        "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
        "build.py": CASE / "build.py",
        "run_native_ssh.ps1": CASE / "run_native_ssh.ps1",
        "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
        "powershell_x86": PS32,
    }
    for name, path in paths.items():
        check(path.is_file() and digest(path) == closure["source_hashes_before"].get(name), f"source SHA {name}")
    check(closure["error"] is None, "closure no error")
    check(len(closure["raw"]) == 24, "24 raw files sealed")
    for name, record in sorted(closure["raw"].items()):
        path = RUN / name
        check(path.is_file() and path.stat().st_size == record["bytes"] and digest(path) == record["sha256"], f"raw seal {name}")

    check(invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"], "session-zero SSH provenance")
    check(invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", "global queue")
    check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, "recorded GUI identity")
    check([step["name"] for step in steps] == ["level2_create", "level1_create", "main_import", "main_export", "positive_calc", "positive_jsonreport", "alternate_calc", "alternate_jsonreport"], "eight guarded steps")
    for step in steps:
        check(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"] is True, f"step {step['name']}")
    first_cwd = Path(invocation["first_working_directory"])
    alternate_cwd = Path(invocation["alternate_working_directory"])
    check(first_cwd == RUN and alternate_cwd != RUN and alternate_cwd == Path(contract["negative_working_directory"]), "two distinct frozen process CWDs")
    check((RUN / "level1.mdb").is_file() and not (alternate_cwd / "level1.mdb").exists(), "include present only under first CWD")
    for step in steps:
        if step["name"] == "positive_calc":
            check(Path(step["working_directory"]) == first_cwd, "positive calc CWD")
        elif step["name"] == "alternate_calc":
            check(Path(step["working_directory"]) == alternate_cwd, "alternate calc CWD")
    original = "mdb=Microsoft Access Driver (*.mdb)|"
    check(invocation["database_association_before"] == original and closure["database_association_after"] == original, "recorded registry original/restored")
    check(invocation["database_association_during_calc"] == "mdb=Microsoft Access Driver (*.mdb, *.accdb)|", "temporary calculation association")
    runner = (CASE / "run_native_ssh.ps1").read_text(encoding="utf-8-sig")
    check("finally" in runner and "Set-ItemProperty" in runner and "Get-ItemPropertyValue" in runner, "sealed registry restore code")
    check("if ((Hash $sxi) -ne $sxiSha)" in runner, "sealed runner checks same SXI before alternate")
    check(digest(RUN / "model.sxi") == closure["sxi_sha256"] == closure["raw"]["model.sxi"]["sha256"], "one sealed SXI across calculations")

    before = populated(parent_input)
    after = populated(main_input)
    check(set(before) == set(after) and len(after) == 11, "11 populated main tables")
    for name in sorted(before.keys() - {"IncludeFiles"}):
        check(before[name] == after[name], f"unchanged main business table {name}")
    old_include = table(parent_input, "model", "IncludeFiles")
    new_include = table(main_input, "model", "IncludeFiles")
    check(old_include["columns"] == new_include["columns"], "IncludeFiles schema retained")
    check(len(new_include["instances"]) == 1 and len(new_include["instances"][0]["rows"]) == 1, "single relative IncludeFiles row")
    check(new_include["instances"][0]["rows"][0] == ["level1.mdb", "Relative level1 at calculation working directory", None], "literal relative level1.mdb")
    check(old_include["instances"][0]["rows"][0][1:] == ["Nested support organization", None], "parent main IncludeFiles description")
    check(level1_source == {"table": "IncludeFiles", "columns": ["INCFN", "INCCO", "NOTE"], "rows": [[str(RUN / "level2.mdb"), "Required base station", None]]}, "level1 nested path source")
    check(level2_source == {"table": "Station", "columns": ["STID", "DESCR", "QTY", "TYPE"], "rows": [["BASE-01", "Teaching base", 1, "WS"]]}, "level2 BASE-01 source")
    for name in ("main-input.json", "level1-source.json", "level2-source.json"):
        check((RUN / name).read_bytes() == (CASE / name).read_bytes(), f"run input copy {name}")
    exported = parse(RUN / "main-roundtrip-raw.json")
    for name, authored in sorted(after.items()):
        actual = table(exported, "model", name)
        columns = [entry["name"] for entry in authored["columns"]]
        output_columns = [entry["name"] for entry in actual["columns"]]
        check(all(column in output_columns for column in columns), f"roundtrip columns {name}")
        indices = [output_columns.index(column) for column in columns]
        for instance in authored["instances"]:
            matching = [entry for entry in actual["instances"] if entry["instance_name"] == instance["instance_name"]]
            check(len(matching) == 1, f"roundtrip instance {name}/{instance['instance_name']}")
            if matching:
                check([[row[index] for index in indices] for row in matching[0]["rows"]] == instance["rows"], f"roundtrip rows {name}/{instance['instance_name']}")

    mdb_hashes = {name: digest(RUN / f"{name}.mdb") for name in ("level1", "level2")}
    mdbs = {"level1": mdb_query(RUN / "level1.mdb", "IncludeFiles"), "level2": mdb_query(RUN / "level2.mdb", "Station")}
    check(mdbs["level1"].get("tables") == ["IncludeFiles"] and mdbs["level1"].get("columns") == ["INCFN", "INCCO", "NOTE"] and mdbs["level1"].get("rows") == level1_source["rows"], "physical level1 MDB")
    check(mdbs["level2"].get("tables") == ["Station"] and mdbs["level2"].get("columns") == ["STID", "DESCR", "QTY", "TYPE"] and mdbs["level2"].get("rows") == level2_source["rows"], "physical level2 MDB")
    for name in ("level1", "level2"):
        check(digest(RUN / f"{name}.mdb") == mdb_hashes[name] == closure["raw"][f"{name}.mdb"]["sha256"], f"read-only {name} MDB unchanged")

    logs = {}
    for arm in ("positive", "alternate"):
        log = (RUN / f"{arm}-run.log").read_text(encoding="utf-8-sig")
        logs[arm] = log
        check(f"Input file: {RUN / 'model.sxi'}" in log, f"{arm} calculation opened same SXI path")
        check(log.count("Including data from file:") == 2 and log.count("Data successfully included") == 2, f"{arm} two nested includes")
        first = log.find("Including data from file:")
        second = log.find("Including data from file:", first + 1)
        normalized_run = str(RUN).replace("\\", "/")
        check(f"{normalized_run}/level1.mdb" in log[first:second] and f"{normalized_run}/level2.mdb" in log[second:], f"{arm} absolute SXI-dir resolution")
        check("IncludeFiles, 1 record inserted" in log[first:second] and "Station, 1 record inserted" in log[second:], f"{arm} nested row insertion")
        check("Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in log, f"{arm} zero-error conversion")
        check(set(re.findall(r"warning #(\d+)", log)) == {"108", "126"}, f"{arm} warning set")
        check((RUN / f"{arm}-model.sxo").stat().st_size > 4, f"{arm} usable SXO")
        check((RUN / f"{arm}-model.log").read_bytes() == (PARENT_RUN / "model.log").read_bytes(), f"{arm} parent event parity")
        check((RUN / f"{arm}-report-raw.json").read_bytes() == (PARENT_RUN / "report-raw.json").read_bytes(), f"{arm} parent report parity")
    check((RUN / "positive-model.log").read_bytes() == (RUN / "alternate-model.log").read_bytes(), "paired event parity")
    check((RUN / "positive-report-raw.json").read_bytes() == (RUN / "alternate-report-raw.json").read_bytes(), "paired report parity")
    check((RUN / "positive-model.sxo").stat().st_size > 4 and (RUN / "alternate-model.sxo").stat().st_size > 4, "both snapshot SXOs usable")
    check((RUN / "model.sxo").read_bytes() == (RUN / "alternate-model.sxo").read_bytes(), "final SXO is alternate snapshot")
    report = parse(RUN / "alternate-report-raw.json")
    rows = {}
    for name in ("SystemResults", "StockTotalResults"):
        record = table(report, "report", name)
        rows[name] = sum(len(instance["rows"]) for instance in record["instances"])
        check(rows[name] == 72, f"72 {name} bins")
    check(len(table(report, "report", "ResultSummary")["instances"][0]["rows"]) == 1, "one summary row")

    verdict = {
        "schema": "independent-readonly-review/v1",
        "case": "K04.var02 v1.0.4",
        "run_id": RUN.name,
        "passed": not failures,
        "verdict": "GO — bounded same-SXI two-CWD relative MDB resolution" if not failures else "NO-GO",
        "checks_passed": checks - len(failures),
        "checks_total": checks,
        "failures": failures,
        "evidence": {
            "closure_sha256": digest(RUN / "closure.json"),
            "sxi_sha256": digest(RUN / "model.sxi"),
            "mdb_sha256": mdb_hashes,
            "independent_odbc": mdbs,
            "model_log_sha256": digest(RUN / "alternate-model.log"),
            "report_sha256": digest(RUN / "alternate-report-raw.json"),
            "report_rows": rows,
            "working_directories": [str(first_cwd), str(alternate_cwd)],
        },
        "limits": [
            "One fixed installed-CLI SXI/MDB pair and two process working directories; the relative top-level level1.mdb resolves under the SXI directory in both observed runs.",
            "The negative working directory lacked level1.mdb at reviewer time and the sealed runner checked its absence before execution; no historical independent filesystem snapshot exists.",
            "The v1.0.0 runner error, v1.0.1 contradicted negative hypothesis, v1.0.2 missing-MDB interactive wait, and v1.0.3 preceding run are excluded from this v1.0.4 acceptance.",
            "No GUI file-dialog/MRU, relative nested include, SXI/OPI include, missing-file general rule, or cross-engine behavior is established.",
            "GUI/registry historical preservation is supported by guarded sealed runner records, not an independent historical observation.",
        ],
    }
    RESULT.write_text(json.dumps(verdict, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{verdict['verdict']}: {verdict['checks_passed']}/{checks}")


if __name__ == "__main__":
    main()
