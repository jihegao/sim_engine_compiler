"""Independent read-only replay of K07 CLI lifecycle and negative boundary."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re


CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
RUN = CASE / "runs" / "k07-var02-cli-evidence-v100-ssh-20261004-01"
PARENT = ROOT / "K02-var01-json-structure-v1.0.1"
PARENT_RUN = PARENT / "runs" / "k02-var01-named-v101-ssh-20261004-01"
RESULT = CASE / "review" / "independent-verdict.json"
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
    for position, char in enumerate(raw):
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
            next_position = position + 1
            while next_position < len(raw) and raw[next_position].isspace():
                next_position += 1
            if next_position == len(raw) or raw[next_position] not in "]}":
                out.append(char)
        else:
            out.append(char)
    return json.loads("".join(out))


def table(doc: dict, section: str, name: str) -> dict:
    matches = [entry for entry in doc[section]["tables"] if entry["name"] == name]
    check(len(matches) == 1, f"unique {section} table {name}")
    return matches[0]


def populated(doc: dict) -> dict[str, dict]:
    return {entry["name"]: entry for entry in doc["model"]["tables"]
            if any(any(value is not None for value in row)
                   for instance in entry.get("instances", [])
                   for row in instance.get("rows", []))}


def main() -> None:
    contract = load(CASE / "contract.json")
    invocation = load(RUN / "invocation.json")
    closure = load(RUN / "closure.json")
    steps = load(RUN / "steps.json")
    outcome = load(RUN / "outcome.json")
    normal_input = load(CASE / "normal-input.json")
    inactive_input = load(CASE / "inactive-base-input.json")
    parent_input = load(PARENT / "named-input.json")
    parent_closure = load(PARENT_RUN / "closure.json")

    check(contract["run_id"] == RUN.name == invocation["run_id"] == closure["run_id"], "frozen run identity")
    parent_pins = {
        "input_sha256": PARENT / "named-input.json",
        "native_sxi_sha256": PARENT_RUN / "model.sxi",
        "closure_sha256": PARENT_RUN / "closure.json",
        "signoff_sha256": PARENT / "cli-scope-signoff-2026-10-04.md",
    }
    for field, path in parent_pins.items():
        check(path.is_file() and sha(path) == contract["dependency"][field], f"accepted K02 {field}")
    check(parent_closure["error"] is None, "accepted K02 closure succeeded")
    check(sha(CASE / "normal-input.json") == contract["inputs_sha256"]["normal"], "normal input contract SHA")
    check(sha(CASE / "inactive-base-input.json") == contract["inputs_sha256"]["inactive_base"], "inactive input contract SHA")
    check((CASE / "normal-input.json").read_bytes() == (PARENT / "named-input.json").read_bytes(), "normal source byte-identical to K02")
    check(sha(RUN / "invocation.json") == closure["invocation_sha256"], "invocation seal")
    check(invocation["source_hashes_before"] == closure["source_hashes_before"] == closure["source_hashes_after"], "source fingerprints stable")
    paths = {
        "contract": CASE / "contract.json",
        "normal": CASE / "normal-input.json",
        "inactive_base": CASE / "inactive-base-input.json",
        "parent_input": PARENT / "named-input.json",
        "parent_sxi": PARENT_RUN / "model.sxi",
        "parent_closure": PARENT_RUN / "closure.json",
        "parent_signoff": PARENT / "cli-scope-signoff-2026-10-04.md",
        "parent_log": PARENT_RUN / "model.log",
        "parent_report": PARENT_RUN / "report-raw.json",
        "exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
        "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
        "build.py": CASE / "build.py",
        "run_native_ssh.ps1": CASE / "run_native_ssh.ps1",
        "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
    }
    for name, path in paths.items():
        check(path.is_file() and sha(path) == closure["source_hashes_before"].get(name), f"source SHA {name}")
    check(closure["error"] is None and outcome["error"] is None, "closure and outcome no audit errors")
    check(len(closure["raw"]) == 23, "23 raw SHA seals")
    for name, seal in sorted(closure["raw"].items()):
        path = RUN / name
        check(path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"], f"raw SHA/size {name}")
    for name in ("normal-input.json", "inactive-base-input.json"):
        check((CASE / name).read_bytes() == (RUN / name).read_bytes(), f"run source copy {name}")

    check(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"], "SSH session-zero provenance")
    check(invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", "host mutex")
    check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, "protected GUI identity")
    expected_steps = ["normal_import", "normal_export", "normal_calc", "normal_report", "copy_convert", "copy_export", "inactive_base_import", "inactive_base_export", "inactive_base_calc"]
    check([step["name"] for step in steps] == expected_steps, "nine guarded native steps")
    for step in steps:
        check(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"] is True, f"step {step['name']}")
    check("-convert" in str(next(step for step in steps if step["name"] == "copy_convert")["arguments"]), "convert command applied to copied SXI")

    check(normal_input == parent_input, "normal model exactly accepted K02")
    main_tables = populated(normal_input)
    inactive_tables = populated(inactive_input)
    check(set(main_tables) == set(inactive_tables) and len(main_tables) == 10, "ten authored row-containing tables")
    for name in sorted(main_tables.keys() - {"Station"}):
        check(main_tables[name] == inactive_tables[name], f"inactive probe unchanged {name}")
    normal_station = table(normal_input, "model", "Station")
    inactive_station = table(inactive_input, "model", "Station")
    check(normal_station["columns"] == inactive_station["columns"], "Station columns unchanged")
    check(len(normal_station["instances"]) == len(inactive_station["instances"]) == 2, "two named Station instances")
    check(normal_station["instances"][0] | {"inactive_rows": [1]} == inactive_station["instances"][0], "only BASE instance gets inactive_rows [1]")
    check(normal_station["instances"][1] == inactive_station["instances"][1], "AUX instance unchanged")

    normal_export = load(RUN / "normal-roundtrip-raw.json")
    convert_export = load(RUN / "convert-roundtrip-raw.json")
    negative_export = load(RUN / "inactive-base-roundtrip-raw.json")
    for name, authored in sorted(main_tables.items()):
        actual = table(normal_export, "model", name)
        source_cols = [column["name"] for column in authored["columns"]]
        output_cols = [column["name"] for column in actual["columns"]]
        check(all(column in output_cols for column in source_cols), f"normal roundtrip columns {name}")
        projection = [output_cols.index(column) for column in source_cols]
        for instance in authored["instances"]:
            matching = [item for item in actual["instances"] if item["instance_name"] == instance["instance_name"]]
            check(len(matching) == 1, f"normal roundtrip instance {name}/{instance['instance_name']}")
            if matching:
                check([[row[index] for index in projection] for row in matching[0]["rows"]] == instance["rows"], f"normal roundtrip rows {name}/{instance['instance_name']}")
    check(normal_export == convert_export, "converted copy remains JSON-readable and same-version roundtrip identical")
    check(sha(RUN / "normal.sxi") == contract["dependency"]["native_sxi_sha256"], "normal imported SXI equals K02")
    check(sha(RUN / "normal.sxi") == sha(RUN / "convert-copy.sxi"), "convert copy byte-identical after same-version convert")
    check((RUN / "convert-copy.sxi").stat().st_size > 4 and (RUN / "convert-roundtrip-raw.json").stat().st_size > 4, "converted copy nonempty/readable")
    check((RUN / "convert.log").stat().st_size == 0, "same-version convert wrote no diagnostic text")
    negative_station = table(negative_export, "model", "Station")
    base_instance = [item for item in negative_station["instances"] if item["instance_name"] == "K02-BASE"]
    check(len(base_instance) == 1 and len(base_instance[0]["rows"]) == 1 and all(value is None for value in base_instance[0]["rows"][0]), "native export blanks inactive BASE row")
    check(not any(item["instance_name"] == "K02-BASE" and "inactive_rows" in item for item in negative_station["instances"]), "native export loses inactive marker")

    normal_log = (RUN / "normal-run.log").read_text(encoding="utf-8-sig")
    check("Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in normal_log, "normal converter zero errors")
    check(re.findall(r"\(warning #(\d+)\)", normal_log) == ["108", "126"], "normal reviewed warnings")
    check((RUN / "normal.sxo").stat().st_size > 4, "normal usable SXO")
    check((RUN / "normal.log").read_bytes() == (PARENT_RUN / "model.log").read_bytes(), "normal event-log K02 parity")
    check((RUN / "normal-report-raw.json").read_bytes() == (PARENT_RUN / "report-raw.json").read_bytes(), "normal report K02 parity")
    events = (RUN / "normal.log").read_text(encoding="utf-8-sig")
    for marker in ("Time: 7 <TEACH-UNIT> mission ordered: BASIC-MISSION", "Time: 8 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission starting", "Time: 11 <BASIC-MISSION,TEACH-UNIT,0,0,0> mission success", "Time: 11 <TEACH-AIR-01,BASE-01,0> System ready"):
        check(marker in events, f"normal mission event {marker[:40]}")
    report = load(RUN / "normal-report-raw.json")
    rows = {}
    for name in ("SystemResults", "StockTotalResults"):
        record = table(report, "report", name)
        rows[name] = sum(len(instance["rows"]) for instance in record["instances"])
        check(rows[name] == 72, f"72 {name} bins")

    negative_log = (RUN / "inactive-base-run.log").read_text(encoding="utf-8-sig")
    errors = re.findall(r"\(error #(\d+)\)", negative_log)
    warnings = re.findall(r"\(warning #(\d+)\)", negative_log)
    notices = re.findall(r"\(notice #(\d+)\)", negative_log)
    check(errors == ["2024", "492", "114", "492"], "inactive exact ordered error codes")
    check(warnings == ["108", "126"] and notices == ["115"], "inactive exact warnings and notice")
    check("Unknown station identifier (STID):  BASE-01" in negative_log, "#2024 BASE-01 attribution")
    check(negative_log.count("Unknown unit or station identifier (USTID):  TEACH-UNIT") == 2, "two #492 TEACH-UNIT attributions")
    check("There are no system units in this problem" in negative_log and "There are no explicit mission units in this problem" in negative_log, "#114/#115 text")
    check("Input conversion completed. Errors: 4, Warnings: 2, Notes: 1" in negative_log, "negative converter summary")
    check((RUN / "inactive-base.sxo").stat().st_size == 4, "negative unusable four-byte SXO")
    check(not (RUN / "inactive-base.log").exists() and not (RUN / "inactive-base-report-raw.json").exists(), "negative no accepted event/report")
    check(outcome["normal"] == outcome["copy_convert"] == "completed" and outcome["inactive_base"] == "completed_rejection" and outcome["negative_converter_summary"] == [4, 2, 1] and outcome["negative_sxo_bytes"] == 4, "outcome classification matches raw")

    verdict = {
        "schema": "independent-readonly-review/v1",
        "case": "K07.var02/var03/var05 v1.0.0",
        "run_id": RUN.name,
        "passed": not failures,
        "verdict": "GO — bounded normal CLI lifecycle, copy-convert readability, and inactive-base converter rejection" if not failures else "NO-GO",
        "checks_passed": checks - len(failures),
        "checks_total": checks,
        "failures": failures,
        "evidence": {
            "closure_sha256": sha(RUN / "closure.json"),
            "normal_sxi_sha256": sha(RUN / "normal.sxi"),
            "convert_copy_sha256": sha(RUN / "convert-copy.sxi"),
            "normal_event_sha256": sha(RUN / "normal.log"),
            "normal_report_sha256": sha(RUN / "normal-report-raw.json"),
            "inactive_error_codes": errors,
            "inactive_warning_codes": warnings,
            "inactive_notice_codes": notices,
            "normal_report_rows": rows,
        },
        "limits": [
            "Normal imported model is the accepted K02 teaching input on this installed CLI; no GUI Test or broader CLI command support is established.",
            "The isolated -convert copy remained readable and byte-identical for the same installed version. No older-version migration behavior is proven.",
            "The inactive-base calculation process exited zero, yet conversion had four errors, a four-byte SXO, and no usable simulation/report. Exit code alone is not acceptance.",
            "Native export blanks the inactive BASE row and omits its inactive_rows marker, so this is not evidence of lossless inactive-row roundtrip.",
            "Host/GUI preservation is evidenced by sealed runner records, not an independent historical process snapshot.",
        ],
    }
    RESULT.write_text(json.dumps(verdict, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{verdict['verdict']}: {verdict['checks_passed']}/{checks}")


if __name__ == "__main__":
    main()
