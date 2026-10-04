"""Read-only K07.var04 cross-reference to four accepted J04 thread runs."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
J03 = ROOT / "J04-var03-nreps-cap-v1.0.0"
J04 = ROOT / "J04-var04-thread-repro-v1.0.0"
FAIL: list[str] = []
CHECKS = 0


def check(ok: bool, name: str) -> None:
    global CHECKS
    CHECKS += 1
    if not ok:
        FAIL.append(name)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native_report(path: Path) -> dict:
    raw = path.read_text(encoding="utf-8-sig")
    check(len(re.findall(r",\s*]", raw)) == 1, f"one preserved native trailing comma {path.parent.name}")
    return json.loads(re.sub(r",\s*]", "]", raw))


def rows_as_dict(table: dict) -> list[dict]:
    names = [col["name"] for col in table["columns"]]
    return [dict(zip(names, row, strict=True)) for instance in table["instances"] for row in instance["rows"]]


contract = read(HERE / "contract.json")
check((contract["case_id"], contract["variant_id"], contract["version"]) == ("K07", "K07.var04", "1.0.0"), "case identity")
check(contract["evidence_mode"].endswith("no new native invocation"), "reuse mode")
linked = {
    "K02_index_sha256": ROOT / "K02-var01-json-structure-v1.0.1/evidence-index.json",
    "K07_cli_workflow_index_sha256": ROOT / "K07-var02-cli-evidence-v1.0.0/evidence-index.json",
    "parent_index_sha256": J03 / "evidence-index.json",
    "thread_study_index_sha256": J04 / "evidence-index.json",
    "thread_study_contract_sha256": J04 / "contract.json",
    "thread_study_independent_verdict_sha256": J04 / "review/independent-readonly-2026-10-01.json",
}
for key, path in linked.items():
    section = contract["instructional_prerequisite"] if key in contract["instructional_prerequisite"] else contract["tested_model"]
    check(path.is_file() and sha(path) == section[key], f"linked source pin {key}")
parent_index = read(J03 / "evidence-index.json")
thread_index = read(J04 / "evidence-index.json")
thread_contract = read(J04 / "contract.json")
independent = read(J04 / "review/independent-readonly-2026-10-01.json")
model = contract["tested_model"]
check(thread_contract["input_sha256"] == model["input_sha256"] and thread_contract["business_delta"].find("-threads 2") >= 0, "J04 frozen thread delta")
check(independent["passed"] is True and independent["check_count"] == 4619 and independent["verdict"] == "GO", "J04 independent accepted verdict")
check([x["run_id"] for x in parent_index["accepted_runs"]] == model["thread_one_run_ids"], "two parent IDs")
check([x["run_id"] for x in thread_index["accepted_runs"]] == model["thread_two_run_ids"], "two thread-two IDs")
check({x["run_id"] for x in thread_index["accepted_runs"]}.isdisjoint({thread_index["excluded_diagnostic"]["run_id"], thread_index["superseded_run"]["run_id"]}), "excluded runs stay excluded")

for package, index in ((J03, parent_index), (J04, thread_index)):
    for name, digest in index["source_files_sha256"].items():
        check(sha(package / name) == digest, f"original source pin {package.name}/{name}")

all_runs = []
for threads, package, index in ((1, J03, parent_index), (2, J04, thread_index)):
    runner = (package / "run_native_ssh.ps1").read_text(encoding="utf-8-sig")
    check(f"-threads {threads}" in runner, f"frozen -threads {threads} runner")
    for entry in index["accepted_runs"]:
        run = package / "runs" / entry["run_id"]
        check(run.is_dir() and Path(entry["local_path"]).resolve() == run.resolve(), f"run path {entry['run_id']}")
        invocation = read(run / "invocation.json")
        closure = read(run / "closure.json")
        manifest = read(run / "run-manifest.json")
        steps = read(run / "steps.json")
        check(sha(run / "invocation.json") == entry["invocation_sha256"] == closure["invocation_sha256"], f"invocation seal {run.name}")
        check(sha(run / "closure.json") == entry["closure_sha256"] == manifest["closure_sha256"], f"closure seal {run.name}")
        check(sha(run / "run-manifest.json") == entry["manifest_sha256"], f"manifest seal {run.name}")
        check(sha(run / "validation.json") == entry["validation_sha256"] == manifest["validation_sha256"], f"validation seal {run.name}")
        check(closure["state"] == "native_steps_complete" and closure["input_sha256"] == model["input_sha256"], f"native complete {run.name}")
        check(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"] and invocation["gui_pid"] == 13340 and invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", f"SSH/GUI/queue {run.name}")
        if threads == 2:
            check(invocation["calc_threads"] == 2 and manifest["calc_threads"] == 2, f"thread-two identity {run.name}")
        check([step["name"] for step in steps] == ["import", "export", "calc", "jsonreport"], f"four native steps {run.name}")
        for step in steps:
            check(step["exit_code"] == 0 and step["coexisting_gui_present_after"], f"completed guarded step {run.name}/{step['name']}")
        check(set(entry["raw"]) == set(closure["raw"]) and len(entry["raw"]) == 11, f"11 raw inventory {run.name}")
        for name, seal in entry["raw"].items():
            path = run / name
            check(path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"] and closure["raw"][name] == seal, f"raw seal {run.name}/{name}")
        check(sha(run / "input.json") == model["input_sha256"], f"same authored input {run.name}")
        check((run / "model.sxo").stat().st_size > 1000, f"nonempty output {run.name}")
        log = (run / "run.log").read_text(encoding="utf-8-sig")
        check(bool(re.search(r"Input conversion completed\. Errors: 0, Warnings: [0-9]+, Notes: 0", log)), f"zero converter errors {run.name}")
        check(sha(run / "report-raw.json") == entry["report_sha256"] == model["report_sha256"], f"raw report equality {run.name}")
        check(sha(run / "model.log") == model["first_replication_log_sha256"], f"first log equality {run.name}")
        report = native_report(run / "report-raw.json")
        report_tables = {table["name"]: table for table in report["report"]["tables"]}
        check({"ResultSummary", "SystemResults", "StockTotalResults"}.issubset(report_tables), f"report tables {run.name}")
        summary = rows_as_dict(report_tables["ResultSummary"])
        check(len(summary) == 1 and summary[0]["NREP"] == 32 and summary[0]["RSMTMF"] == 0.11425267904996872, f"NREP32 result {run.name}")
        for table_name in ("SystemResults", "StockTotalResults"):
            check(len(rows_as_dict(report_tables[table_name])) == 72, f"72 bins {run.name}/{table_name}")
        all_runs.append({"run_id": run.name, "threads": threads, "closure_sha256": entry["closure_sha256"]})

check(len(all_runs) == 4 and {r["threads"] for r in all_runs} == {1, 2}, "four accepted runs across two counts")
verdict = {
    "schema": "simlox-k07-var04-author-cross-reference/v1",
    "verdict": "GO_BOUNDED" if not FAIL else "NO_GO",
    "passed": not FAIL,
    "checks_passed": CHECKS - len(FAIL),
    "checks_total": CHECKS,
    "failures": FAIL,
    "reused_native_runs": all_runs,
    "raw_seals_rechecked": 44,
    "limits": contract["limits"],
}
destination = HERE / "review/author-validation-2026-10-05.json"
destination.parent.mkdir(exist_ok=True)
destination.write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8")
print(f"{verdict['verdict']} {verdict['checks_passed']}/{CHECKS}")
for failure in FAIL:
    print(failure)
raise SystemExit(0 if not FAIL else 1)
