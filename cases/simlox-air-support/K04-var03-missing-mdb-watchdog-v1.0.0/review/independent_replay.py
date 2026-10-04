"""Independent read-only replay of the K04.var03 missing-MDB watchdog diagnostic."""

from __future__ import annotations

from datetime import datetime
import hashlib
import json
from pathlib import Path


CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parent
RUN = CASE / "runs" / "k04-var03-missing-mdb-v100-ssh-20261004-01"
PARENT = ROOT / "K04-var02-relative-cwd-v1.0.4"
PARENT_RUN = PARENT / "runs" / "k04-var02-relative-cwd-v104-ssh-20261004-01"
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
    return json.loads(path.read_text(encoding="utf-8-sig"))


def seconds(a: str, b: str) -> float:
    return (datetime.fromisoformat(b.replace("Z", "+00:00")) - datetime.fromisoformat(a.replace("Z", "+00:00"))).total_seconds()


def main() -> None:
    contract = load(CASE / "contract.json")
    invocation = load(RUN / "invocation.json")
    closure = load(RUN / "closure.json")
    observation = load(RUN / "observation.json")
    parent_closure = load(PARENT_RUN / "closure.json")
    parent_input = load(PARENT / "main-input.json")

    check(contract["run_id"] == RUN.name == invocation["run_id"] == closure["run_id"] == observation["run_id"], "run identity")
    check(contract["watchdog_ms"] == invocation["watchdog_ms"] == [20000, 25000], "predeclared watchdog intervals")
    check(contract["dependency"]["package"] == PARENT.name, "accepted parent package")
    parent_paths = {
        "sxi_sha256": PARENT_RUN / "model.sxi",
        "closure_sha256": PARENT_RUN / "closure.json",
        "signoff_sha256": PARENT / "cli-scope-signoff-2026-10-04.md",
        "main_input_sha256": PARENT / "main-input.json",
        "positive_event_sha256": PARENT_RUN / "positive-model.log",
        "positive_report_sha256": PARENT_RUN / "positive-report-raw.json",
    }
    for key, path in parent_paths.items():
        check(path.is_file() and sha(path) == contract["dependency"][key], f"accepted parent {key}")
    check(parent_closure["error"] is None, "accepted parent successful")
    include = [entry for entry in parent_input["model"]["tables"] if entry["name"] == "IncludeFiles"]
    check(len(include) == 1 and include[0]["instances"][0]["rows"][0][0] == "level1.mdb", "parent SXI relative IncludeFiles source")
    check(sha(RUN / "model.sxi") == sha(PARENT_RUN / "model.sxi") == contract["dependency"]["sxi_sha256"], "copied SXI byte-identical to accepted parent")
    check(invocation["model_sxi_sha256"] == contract["dependency"]["sxi_sha256"], "invocation SXI fingerprint")

    check(sha(RUN / "invocation.json") == closure["invocation_sha256"], "invocation seal")
    check(invocation["source_hashes_before"] == closure["source_hashes_before"] == closure["source_hashes_after"], "source hashes stable")
    source_paths = {
        "contract": CASE / "contract.json",
        "parent_sxi": PARENT_RUN / "model.sxi",
        "parent_closure": PARENT_RUN / "closure.json",
        "parent_signoff": PARENT / "cli-scope-signoff-2026-10-04.md",
        "parent_main": PARENT / "main-input.json",
        "parent_event": PARENT_RUN / "positive-model.log",
        "parent_report": PARENT_RUN / "positive-report-raw.json",
        "exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
        "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
        "runner": CASE / "run_native_ssh.ps1",
        "parent_level1_mdb": PARENT_RUN / "level1.mdb",
    }
    for name, path in source_paths.items():
        check(path.is_file() and sha(path) == closure["source_hashes_before"].get(name), f"source SHA {name}")
    check(closure["error"] is None, "closure no audit error")
    check(closure["outcome"] == observation["outcome"] == "watchdog_terminated_after_45_seconds", "watchdog termination classification")
    check(len(closure["raw"]) == 5, "five sealed raw files")
    for name, record in sorted(closure["raw"].items()):
        path = RUN / name
        check(path.is_file() and path.stat().st_size == record["bytes"] and sha(path) == record["sha256"], f"raw file seal {name}")
    check(sha(RUN / "$5460@model.sxi$") == sha(RUN / "model.sxi"), "temporary SXI artifact exact copy")

    check(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"], "recorded session-zero SSH")
    check(invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue", "host native queue")
    check(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1, "protected GUI identity")
    check(invocation["run_dir"] == str(RUN) and invocation["model_directory"] == str(RUN), "isolated SXI directory")
    check(invocation["working_directory"] == str(PARENT_RUN) and Path(invocation["working_directory"]) != RUN, "requested distinct process working directory")
    missing = RUN / "level1.mdb"
    existing = PARENT_RUN / "level1.mdb"
    check(invocation["missing_file"] == str(missing) and not missing.exists(), "MDB absent beside copied SXI")
    check(invocation["existing_working_directory_file"] == str(existing) and existing.is_file(), "MDB present in requested working directory")
    check(sha(existing) == closure["source_hashes_before"]["parent_level1_mdb"] == parent_closure["raw"]["level1.mdb"]["sha256"], "working directory MDB accepted seal")
    check(str(RUN / "model.sxi") in invocation["arguments"] and "-calc" in invocation["arguments"], "one calc command for isolated SXI")
    original = "mdb=Microsoft Access Driver (*.mdb)|"
    check(invocation["association_before"] == closure["association_after"] == observation["association_after"] == original, "recorded MDB association restored")
    check(invocation["association_during"] == "mdb=Microsoft Access Driver (*.mdb, *.accdb)|", "recorded temporary MDB association")
    runner = (CASE / "run_native_ssh.ps1").read_text(encoding="utf-8-sig")
    for marker in ("Assert-Child", "Stop-Process -Id $childPid", "-WindowStyle Hidden", "$child.WaitForExit(20000)", "$child.WaitForExit(25000)", "Set-ItemProperty", "Assert-Gui"):
        check(marker in runner, f"sealed guarded runner {marker}")

    snapshots = observation["timed_snapshots"]
    check(len(snapshots) == 2 and [snap["label"] for snap in snapshots] == ["after_20_seconds_or_exit", "after_45_seconds_or_exit"], "two timed snapshots")
    for snap in snapshots:
        check(snap["child_pid"] == observation["child_pid"] == 5460 and snap["child_alive"] is True, f"{snap['label']} same live child")
        check(snap["child_name"] == "Simlox.exe" and snap["child_session_id"] == 0, f"{snap['label']} session-zero Simlox identity")
        check(str(RUN / "model.sxi") in snap["child_command_line"] and "-calc" in snap["child_command_line"], f"{snap['label']} child command line")
        check(snap["files"] == {"model.sxi": 189416, "model.sxo": 4, "run.log": 679, "model.log": None}, f"{snap['label']} partial output sizes")
        check(snap["main_window_handle"] == "0" and snap["main_window_title"] == "", f"{snap['label']} no visible child main window recorded")
    check(snapshots[0]["child_cpu_seconds"] == snapshots[1]["child_cpu_seconds"] == 0.515625, "no CPU progress between snapshots")
    check(18 <= seconds(invocation["created_utc"], snapshots[0]["observed_utc"]) <= 23, "first snapshot near 20 seconds")
    check(43 <= seconds(invocation["created_utc"], snapshots[1]["observed_utc"]) <= 49, "second snapshot near 45 seconds")
    check(24 <= seconds(snapshots[0]["observed_utc"], snapshots[1]["observed_utc"]) <= 27, "second watchdog wait near 25 seconds")
    final = observation["final_snapshot"]
    check(final["label"] == "after_child_exit" and final["child_pid"] == 5460 and final["child_alive"] is False, "targeted child no longer alive")
    check(final["files"] == snapshots[1]["files"], "no output advancement by termination")
    check(observation["watchdog_stopped_only_verified_child"] is True and observation["gui_preserved"] is True, "recorded targeted stop and GUI preservation")
    check(observation["exit_code"] == -1 and observation["error"] is None, "watchdog exit distinct from native diagnostic")

    runlog = (RUN / "run.log").read_text(encoding="utf-8-sig")
    check("Converting input data ..." in runlog and "Including data from file:" in runlog, "converter reached missing include")
    check(str(missing).replace("\\", "/") in runlog, "native attempted SXI-directory path")
    check("Input conversion completed" not in runlog and "error #" not in runlog and "Data successfully included" not in runlog, "no terminal converter result recorded")
    check((RUN / "model.sxo").stat().st_size == 4, "four-byte unusable SXO")
    check(not (RUN / "model.log").exists() and not (RUN / "report-raw.json").exists(), "no simulation log or report")

    result = {
        "schema": "independent-readonly-review/v1",
        "case": "K04.var03 v1.0.0",
        "run_id": RUN.name,
        "passed": not failures,
        "verdict": "GO — bounded watchdog nontermination diagnostic; NO-GO for a native terminal missing-file behavior claim" if not failures else "NO-GO — diagnostic evidence mismatch",
        "checks_passed": checks - len(failures),
        "checks_total": checks,
        "failures": failures,
        "evidence": {
            "closure_sha256": sha(RUN / "closure.json"),
            "copied_sxi_sha256": sha(RUN / "model.sxi"),
            "observation_sha256": sha(RUN / "observation.json"),
            "run_log_sha256": sha(RUN / "run.log"),
            "watchdog_snapshots_utc": [snap["observed_utc"] for snap in snapshots],
            "child_pid": observation["child_pid"],
            "sxo_bytes": (RUN / "model.sxo").stat().st_size,
        },
        "limits": [
            "This one session-zero CLI child remained live with unchanged partial outputs at roughly 20 and 45 seconds and was then forcibly stopped by the guarded watchdog; it did not emit a native terminal missing-file outcome.",
            "No modal dialog is inferred. The snapshots recorded an empty child main-window title and handle 0; other hidden interaction states were not observed.",
            "The requested process working directory held level1.mdb, while the copied SXI directory did not. This supports an SXI-directory path attempt in this run, not a universal path-resolution or missing-file rule.",
            "GUI, mutex and MDB association preservation are sealed runner observations; historical host state was not independently sampled by this replay.",
        ],
    }
    RESULT.write_text(json.dumps(result, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"{result['verdict']}: {result['checks_passed']}/{checks}")


if __name__ == "__main__":
    main()
