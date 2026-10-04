"""Read-only K07.var04 cross-reference replay of four accepted J04 runs."""
import hashlib
import json
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
REPO = HERE.parents[2]
CASES = HERE.parent
J03 = CASES / "J04-var03-nreps-cap-v1.0.0"
J04 = CASES / "J04-var04-thread-repro-v1.0.0"
K02 = CASES / "K02-var01-json-structure-v1.0.1"
K07_CLI = CASES / "K07-var02-cli-evidence-v1.0.0"
VERDICT_PATH = Path(__file__).with_name("independent-verdict.json")
checks = 0
failures = []


def check(value, label):
    global checks
    checks += 1
    if not value:
        failures.append(label)


def sha_bytes(data):
    return hashlib.sha256(data).hexdigest()


def sha(path):
    return sha_bytes(path.read_bytes())


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def git_blob(path):
    relative = path.relative_to(REPO).as_posix()
    result = subprocess.run(["git", "show", "HEAD:" + relative], cwd=REPO, capture_output=True, check=False)
    check(result.returncode == 0, f"Git HEAD blob exists: {relative}")
    return result.stdout if result.returncode == 0 else b""


contract = load(HERE / "contract.json")
idx03 = load(J03 / "evidence-index.json")
idx04 = load(J04 / "evidence-index.json")
thread = contract["tested_model"]
check(contract["evidence_mode"] == "source-bound reuse of accepted native runs; no new native invocation", "cross-reference mode")
check(contract["instructional_prerequisite"]["role"].endswith("not the thread-study model parent."), "instructional versus tested parent")
check(thread["parent_case"] == "J04.var03@1.0.0" and thread["thread_study_case"] == "J04.var04@1.0.0", "tested J04 lineage")
for label, path, wanted in [
    ("K02 instructional index", K02 / "evidence-index.json", contract["instructional_prerequisite"]["K02_index_sha256"]),
    ("K07 CLI instructional index", K07_CLI / "evidence-index.json", contract["instructional_prerequisite"]["K07_cli_workflow_index_sha256"]),
    ("J04 parent index", J03 / "evidence-index.json", thread["parent_index_sha256"]),
    ("J04 thread index", J04 / "evidence-index.json", thread["thread_study_index_sha256"]),
    ("J04 thread contract", J04 / "contract.json", thread["thread_study_contract_sha256"]),
    ("J04 independent verdict", J04 / "review/independent-readonly-2026-10-01.json", thread["thread_study_independent_verdict_sha256"]),
]:
    check(path.is_file() and sha(path) == wanted, label + " disk SHA")
    check(sha_bytes(git_blob(path)) == wanted, label + " Git byte SHA")

for package, index in [(J03, idx03), (J04, idx04)]:
    check(index["case_id"] == "J04", f"{package.name} index case")
    for relative, wanted in sorted(index["source_files_sha256"].items()):
        path = package / relative
        check(path.is_file() and sha(path) == wanted, f"source disk {package.name}/{relative}")
        check(sha_bytes(git_blob(path)) == wanted, f"source Git {package.name}/{relative}")

parent_source = J03 / "probe-input.json"
thread_source = J04 / "probe-input.json"
check(sha(parent_source) == sha(thread_source) == thread["input_sha256"], "same exact J04 model bytes")
source = load(parent_source)
control = next(t for t in source["model"]["tables"] if t["name"] == "Control")
control_fields = {column["name"]: value for column, value in zip(control["columns"], control["instances"][0]["rows"][0])}
check(control_fields["NREPS"] == thread["configured_repetitions"] == 32, "source NREPS32")
check(control_fields["RSEED"] == thread["seed"] == "1", "source seed one")
check(idx03["variant_id"] == "J04.var03" and idx04["variant_id"] == "J04.var04", "distinct J04 catalog variants")
check(sha(J04 / "review/independent-readonly-2026-10-01.json") == thread["thread_study_independent_verdict_sha256"], "independent verdict SHA")
check(load(J04 / "review/independent-readonly-2026-10-01.json")["passed"] is True, "prior independent verdict passed")

expected_ones = thread["thread_one_run_ids"]
expected_twos = thread["thread_two_run_ids"]
check(len(expected_ones) == len(expected_twos) == 2 and len(set(expected_ones + expected_twos)) == 4, "four distinct accepted IDs")
check({entry["run_id"] for entry in idx03["accepted_runs"]} == set(expected_ones), "parent accepted set")
check({entry["run_id"] for entry in idx04["accepted_runs"]} == set(expected_twos), "thread2 accepted set")
check({entry["run_id"] for entry in idx04["parent_thread_one_runs"]} == set(expected_ones), "thread index parent set")
excluded_ids = {idx04["excluded_diagnostic"]["run_id"], idx04["superseded_run"]["run_id"]}
check(excluded_ids == {"j04-var04-thread2-probe-20261001-01", "j04-var04-thread2-accepted-20261001-01"}, "diagnostic/superseded identification")
check(not excluded_ids.intersection(expected_ones + expected_twos), "excluded runs not accepted")
check(idx04["excluded_diagnostic"]["role"] == "excluded_diagnostic" and idx04["superseded_run"]["role"] == "superseded_not_published", "excluded roles")
check(not (J04 / "runs/j04-var04-thread2-accepted-20261001-01/run-manifest.json").exists(), "superseded manifest absent")
check(not (J04 / "runs/j04-var04-thread2-accepted-20261001-01/validation.json").exists(), "superseded validation absent")

all_reports = []
all_first_logs = []
raw_count = 0
for expected_threads, package, index, ids in [(1, J03, idx03, expected_ones), (2, J04, idx04, expected_twos)]:
    runner = (package / "run_native_ssh.ps1").read_text(encoding="utf-8-sig")
    check(re.search(r"-threads\s+" + str(expected_threads) + r"\s+-calc", runner) is not None, f"runner CLI -threads {expected_threads}")
    for run_id in ids:
        directory = package / "runs" / run_id
        indexed = next(entry for entry in index["accepted_runs"] if entry["run_id"] == run_id)
        closure = load(directory / "closure.json")
        invocation = load(directory / "invocation.json")
        manifest = load(directory / "run-manifest.json")
        validation = load(directory / "validation.json")
        steps = load(directory / "steps.json")
        check(indexed["role"] in {"current_accepted", "parent_accepted"}, f"index accepted role {run_id}")
        check(closure["run_id"] == invocation["run_id"] == manifest["run_id"] == run_id, f"run identities {run_id}")
        check(closure["state"] == "native_steps_complete" and manifest["execution_mode"] == "ssh_cli_v1", f"native closure/manifest {run_id}")
        check(sha(directory / "closure.json") == indexed["closure_sha256"] == manifest["closure_sha256"], f"closure pin {run_id}")
        check(sha(directory / "invocation.json") == indexed["invocation_sha256"] == closure["invocation_sha256"], f"invocation pin {run_id}")
        check(sha(directory / "validation.json") == indexed["validation_sha256"] == manifest["validation_sha256"], f"validation pin {run_id}")
        check(sha(directory / "run-manifest.json") == indexed["manifest_sha256"], f"manifest pin {run_id}")
        check(validation.get("passed") is True, f"validation passed {run_id}")
        check(closure["input_sha256"] == invocation["input_sha256"] == manifest["input_sha256"] == indexed["input_sha256"] == thread["input_sha256"], f"source binding {run_id}")
        check(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"] and invocation["gui_pid"] == 13340 and invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", f"SSH0 GUI mutex {run_id}")
        check(invocation.get("calc_threads", 1) == expected_threads and manifest.get("calc_threads", 1) == expected_threads, f"thread invocation/manifest {run_id}")
        check(invocation["runner_sha256"] == closure["post_source_sha256"]["run_native_ssh.ps1"] == sha(package / "run_native_ssh.ps1"), f"pinned calc command runner {run_id}")
        check([step["name"] for step in steps] == ["import", "export", "calc", "jsonreport"], f"four ordered CLI steps {run_id}")
        for step in steps:
            check(step["exit_code"] == 0 and step["coexisting_gui_present_after"] is True, f"step exit/GUI {run_id}/{step['name']}")
        check(len(closure["raw"]) == len(indexed["raw"]) == 11, f"eleven raw files {run_id}")
        check(closure["raw"] == indexed["raw"], f"index raw map {run_id}")
        for filename, record in sorted(closure["raw"].items()):
            path = directory / filename
            check(path.is_file(), f"raw exists {run_id}/{filename}")
            if path.is_file():
                check(path.stat().st_size == record["bytes"], f"raw bytes {run_id}/{filename}")
                check(sha(path) == record["sha256"], f"raw SHA {run_id}/{filename}")
            raw_count += 1
        check(sha(directory / "input.json") == thread["input_sha256"], f"input bytes {run_id}")
        log = (directory / "run.log").read_text(encoding="utf-8-sig")
        check("Input conversion completed. Errors: 0, Warnings: 3, Notes: 0" in log, f"converter zero errors {run_id}")
        check(re.findall(r"\(warning #(\d+)\)", log) == ["108", "211", "126"], f"reviewed warnings {run_id}")
        check((directory / "model.sxo").stat().st_size > 100000, f"nonempty result {run_id}")
        report_path = directory / "report-raw.json"
        first_log_path = directory / "model.log"
        check(sha(report_path) == indexed["report_sha256"] == thread["report_sha256"], f"report pin {run_id}")
        indexed_first_log = indexed.get("first_replication_log_sha256", indexed["raw"]["model.log"]["sha256"])
        check(sha(first_log_path) == indexed_first_log == thread["first_replication_log_sha256"], f"first log pin {run_id}")
        all_reports.append(report_path.read_bytes())
        all_first_logs.append(first_log_path.read_bytes())

check(raw_count == 44, "44 raw seals across accepted runs")
check(len(set(all_reports)) == 1, "four reports byte-identical")
check(len(set(all_first_logs)) == 1, "four first-replication logs byte-identical")
check(all(b"Time:" in event for event in all_first_logs), "first-replication event content")
check("No fresh K07 or K02-specific thread run." in contract["limits"], "no new run claim")
check(any("remaining 31" in item or "remaining thirty-one" in item for item in contract["limits"]), "first-only log limit")

verdict = {
    "schema": "simlox-k07-var04-independent-cross-reference-verdict/v1",
    "case_id": "K07.var04",
    "verdict": "GO_BOUNDED" if not failures else "NO_GO",
    "checks_passed": checks - len(failures),
    "checks_total": checks,
    "failures": failures,
    "accepted_run_ids": expected_ones + expected_twos,
    "accepted_raw_seals": raw_count,
    "excluded_run_ids": sorted(excluded_ids),
    "finding": "Two accepted -threads 1 and two accepted -threads 2 J04 runs use the same seed-one NREPS32 input; raw JSON reports and first-replication event logs are byte-identical.",
    "limits": ["K02 and K07 CLI evidence is instructional; tested model lineage is J04.var03 to J04.var04.", "No fresh K07 run; the other 31 replication event histories are not exposed by ENLOG.", "No general parallel determinism, performance scaling, other threads/seeds, GUI, or cross-engine conclusion.", "Legacy raw JSON report is compared by bytes; strict JSON parsing is not asserted."],
}
VERDICT_PATH.write_text(json.dumps(verdict, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(json.dumps({"verdict": verdict["verdict"], "checks": f"{verdict['checks_passed']}/{checks}", "failures": failures, "script_sha256": sha(Path(__file__)), "verdict_sha256": sha(VERDICT_PATH)}, indent=2))
