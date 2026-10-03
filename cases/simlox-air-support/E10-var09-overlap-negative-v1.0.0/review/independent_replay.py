"""Independent, read-only replay of the E10.var09 converter rejection.

This script uses only the Python standard library and the sealed model/run files.
It neither invokes SIMLOX nor imports the case author's implementation.
"""

from __future__ import annotations

import hashlib
import json
import re
import sys
from pathlib import Path


CASE = Path(__file__).resolve().parent.parent
ROOT = CASE.parent
PARENT = ROOT / "E10-var03-ondem-support-gap-v1.0.0"
RUN = CASE / "runs" / "e10-var09-overlap-v100-ssh-20261003-01"
PARENT_RUN = PARENT / "runs" / "e10-var03-gap-v100-ssh-20261003-01"
OUT = Path(__file__).with_name("independent-verdict.json")


class Audit:
    def __init__(self) -> None:
        self.passed = 0
        self.failures: list[str] = []

    def check(self, condition: bool, description: str) -> None:
        if condition:
            self.passed += 1
        else:
            self.failures.append(description)

    def equal(self, actual: object, expected: object, description: str) -> None:
        self.check(actual == expected, f"{description}: expected {expected!r}, got {actual!r}")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict | list:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def tables(path: Path) -> dict[str, dict]:
    return {table["name"]: table for table in read_json(path)["model"]["tables"]}


def all_rows(table: dict) -> list[list]:
    return [row for instance in table.get("instances", []) for row in instance.get("rows", [])]


def run() -> dict:
    a = Audit()
    contract = read_json(CASE / "contract.json")
    diff = read_json(CASE / "exact-diff.json")
    invoke = read_json(RUN / "invocation.json")
    closure = read_json(RUN / "closure.json")
    steps = read_json(RUN / "steps.json")
    source = tables(CASE / "native-input.json")
    parent = tables(PARENT / "native-input.json")
    export = tables(RUN / "roundtrip-raw.json")

    a.equal(contract["variant_id"], "E10.var09", "contract identity")
    a.equal(diff["changed_tables"], ["ProblemDescription", "TransportPolicyProfile"], "declared table delta")
    a.equal(digest(CASE / "native-input.json"), contract["native_input_sha256"], "child input pin")
    a.equal(digest(CASE / "exact-diff.json"), contract["exact_diff_sha256"], "diff pin")
    a.equal(digest(PARENT / "native-input.json"), contract["accepted_parent"]["input_sha256"], "accepted parent input pin")
    a.equal(digest(PARENT_RUN / "closure.json"), contract["accepted_parent"]["native_closure_sha256"], "accepted parent closure pin")
    a.equal(digest(PARENT / "evidence-index.json"), contract["accepted_parent"]["evidence_index_sha256"], "accepted parent index pin")
    a.equal(digest(Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")), contract["source"]["simlox_exe_sha256"], "installed executable pin")
    a.equal(digest(Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")), contract["source"]["manual_pdf_sha256"], "installed manual pin")
    a.equal(digest(Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")), contract["source"]["dictionary_sha256"], "installed dictionary pin")

    a.equal(set(source), set(parent), "parent/child table identities")
    a.equal(len(source), 32, "source table count")
    for name in sorted(parent):
        if name not in {"ProblemDescription", "TransportPolicyProfile"}:
            a.equal(source[name], parent[name], f"unchanged parent table {name}")
    a.equal(source["ProblemDescription"]["columns"], parent["ProblemDescription"]["columns"], "description schema")
    a.check(all_rows(source["ProblemDescription"]) != all_rows(parent["ProblemDescription"]), "description text changed")
    a.equal(len(all_rows(source["ProblemDescription"])), 1, "one description row")
    a.equal(len(all_rows(parent["ProblemDescription"])), 1, "one parent description row")

    child_policy = source["TransportPolicyProfile"]
    parent_policy = parent["TransportPolicyProfile"]
    a.equal(child_policy["columns"], parent_policy["columns"], "transport policy schema")
    cols = [column["name"] for column in child_policy["columns"]]
    a.equal(cols, ["TPRID", "STPRID", "STIM", "IQTY", "IINT", "DURN", "MINBS", "TPTIM", "TPTIMD", "NOTE"], "policy column order")
    cr = all_rows(child_policy)
    pr = all_rows(parent_policy)
    a.equal(len(cr), 2, "child policy row count")
    a.equal(len(pr), 2, "parent policy row count")
    durn = cols.index("DURN")
    changed_cells = [(i, cols[j], old, new) for i, (old_row, new_row) in enumerate(zip(pr, cr)) for j, (old, new) in enumerate(zip(old_row, new_row)) if old != new]
    a.equal(changed_cells, [(0, "DURN", 9.0, 12.0)], "only business cell change")
    a.equal(cr[1], pr[1], "second ONDEM row unchanged")
    a.equal(cr[0][0:3], ["DOWN-POLICY", "ONDEM", 0.0], "first policy identity/start")
    a.equal(cr[1][0:3], ["DOWN-POLICY", "ONDEM", 11.0], "second policy identity/start")
    a.equal(cr[0][2] + cr[0][durn], 12.0, "child first policy end")
    a.equal(pr[0][2] + pr[0][durn], 9.0, "parent first policy end")
    a.equal(cr[1][2], 11.0, "second policy start")
    a.equal(cr[0][2] + cr[0][durn] - cr[1][2], 1.0, "one-hour overlap")
    a.equal(diff["first_window_change"]["DURN"], [9.0, 12.0], "diff first duration")
    a.equal(diff["second_window_unchanged"], cr[1], "diff second row")

    a.equal(invoke["input_sha256"], digest(CASE / "native-input.json"), "invocation input")
    a.equal(invoke["run_id"], RUN.name, "invocation run identity")
    a.equal(invoke["execution_mode"], "ssh_cli_v1", "SSH mode")
    a.equal(invoke["session_id"], 0, "headless session")
    a.check(invoke["ssh_connection_present"] is True, "SSH connection recorded")
    a.check("sshd.exe" in invoke["ssh_ancestor_names"], "SSH ancestor recorded")
    a.equal(invoke["queue_mutex"], r"Global\SimloxIssue18NativeQueue", "native queue mutex")
    a.equal(invoke["gui"]["pid"], 13340, "preserved GUI PID")
    a.equal(invoke["gui"]["session_id"], 1, "GUI session separate")
    a.equal(closure["error"], None, "closure error")
    a.equal(closure["scope"], "expected_negative_conversion_candidate", "negative run classification")
    a.equal(closure["invocation_sha256"], digest(RUN / "invocation.json"), "invocation seal")
    a.equal(closure["source_hashes_before"], closure["source_hashes_after"], "source stability")
    a.equal(closure["source_hashes_before"], invoke["source_hashes_before"], "invocation source seal")
    source_files = {
        "input": CASE / "native-input.json",
        "parent": PARENT / "native-input.json",
        "parent_closure": PARENT_RUN / "closure.json",
        "parent_index": PARENT / "evidence-index.json",
        "contract": CASE / "contract.json",
        "exact_diff": CASE / "exact-diff.json",
        "builder": CASE / "build.py",
        "diff_builder": CASE / "describe_diff.py",
        "checker": CASE / "check_roundtrip.py",
        "runner_script": CASE / "run_native_ssh.ps1",
        "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
        "simlox_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
        "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
        "dictionary": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
    }
    for name, path in sorted(source_files.items()):
        a.equal(closure["source_hashes_before"][name], digest(path), f"frozen source {name}")
    for name, entry in sorted(closure["raw"].items()):
        path = RUN / name
        a.check(path.is_file(), f"raw artifact exists: {name}")
        if path.is_file():
            a.equal(path.stat().st_size, entry["bytes"], f"raw size: {name}")
            a.equal(digest(path), entry["sha256"], f"raw SHA: {name}")
    a.equal(set(closure["raw"]), {"input.json", "model.sxi", "model.sxo", "import.log", "export.log", "run.log", "roundtrip-raw.json", "roundtrip-validation.json", "steps.json"}, "negative-run raw inventory")
    a.equal(digest(RUN / "input.json"), digest(CASE / "native-input.json"), "run input copy")

    a.equal([step["name"] for step in steps], ["import", "export", "calc", "check_import_export"], "four negative-run steps")
    for step in steps:
        a.equal(step["exit_code"], 0, f"{step['name']} process exit")
        a.equal(step["status"], "completed", f"{step['name']} recorded completion")
        a.check(step["gui_preserved"] is True, f"{step['name']} GUI preservation")
        a.equal(step["error"], None, f"{step['name']} step error")
    for step in steps[:3]:
        a.check("-silent" in step["arguments"] and "-close" in step["arguments"], f"{step['name']} headless CLI flags")
    a.check("-calc" in steps[2]["arguments"] and "-threads 1" in steps[2]["arguments"], "calc command and thread count")
    a.equal([command["name"] for command in invoke["planned_commands"]], ["import", "export", "calc"], "planned command sequence")

    authored = [name for name, table in source.items() if all_rows(table)]
    a.equal(len(authored), 22, "22 authored row-containing tables")
    a.equal(set(export), set(source), "native export table names")
    for name in sorted(authored):
        a.equal(export[name], source[name], f"independent exact roundtrip: {name}")
    a.equal(digest(RUN / "roundtrip-raw.json"), closure["raw"]["roundtrip-raw.json"]["sha256"], "native export seal")

    parent_log = (PARENT_RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    log = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    a.check("Input conversion completed. Errors: 0, Warnings: 1, Notes: 0" in parent_log, "accepted parent zero-error conversion")
    a.check("(error #" not in parent_log, "accepted parent has no converter error")
    a.check("Input conversion completed. Errors: 1, Warnings: 1, Notes: 0" in log, "child conversion counts")
    a.equal(re.findall(r"\(error #(\d+)\) ([^\r\n]+)", log), [("153", "FIX transports during ONDEM period in profile: DOWN-POLICY")], "exact child converter error")
    a.equal(re.findall(r"\(warning #(\d+)\) ([^\r\n]+)", log), [("108", "Enabling simulation log may generate extensive data in log file")], "exact converter warning")
    a.check("Form: TransportPolicyProfile\nrec 1:" in log.replace("\r\n", "\n"), "error form and record")
    a.equal((RUN / "model.sxo").stat().st_size, 4, "unusable SXO size")
    for name in ("model.log", "report-raw.json", "report.json"):
        a.check(not (RUN / name).exists(), f"no simulation artifact: {name}")

    result = {
        "schema": "simlox-independent-readonly-review/v1",
        "case_id": "E10.var09",
        "run_id": RUN.name,
        "passed": not a.failures,
        "verdict": "GO: bounded source-bound converter rejection" if not a.failures else "NO-GO: independent replay mismatch",
        "checks_passed": a.passed,
        "checks_total": a.passed + len(a.failures),
        "failures": a.failures,
        "observations": {
            "accepted_parent_zero_errors": True,
            "source_delta": "ProblemDescription and first TransportPolicyProfile.DURN 9->12 only",
            "policy_windows_hours": [[0, 12], [11, 36]],
            "native_error": "TransportPolicyProfile rec 1 error #153: FIX transports during ONDEM period in profile: DOWN-POLICY",
            "native_calc_exit_code": steps[2]["exit_code"],
            "sxo_bytes": (RUN / "model.sxo").stat().st_size,
            "source_row_tables_exact_roundtrip": len(authored),
            "run_closure_sha256": digest(RUN / "closure.json"),
        },
        "limits": [
            "One one-hour overlap of two ONDEM windows in DOWN-POLICY on this installed CLI.",
            "Process exit 0 did not mean simulation success: conversion had one error, SXO is four bytes, and no event log or report exists.",
            "No claim about overlap priority, other policy types, valid touching boundaries, nested profiles, GUI-only use, or another engine version.",
        ],
    }
    OUT.write_bytes((json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    return result


if __name__ == "__main__":
    result = run()
    print(json.dumps({key: result[key] for key in ("verdict", "checks_passed", "checks_total", "failures")}, indent=2))
    sys.exit(0 if result["passed"] else 1)
