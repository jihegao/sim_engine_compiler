"""Read-only author replay for the bounded K04.var03 missing-MDB watchdog run."""
import hashlib
import json
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE / "runs" / "k04-var03-missing-mdb-v100-ssh-20261004-01"
PARENT = HERE.parent / "K04-var02-relative-cwd-v1.0.4"
PARENT_RUN = PARENT / "runs" / "k04-var02-relative-cwd-v104-ssh-20261004-01"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def stamp(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def check(value, label, names):
    if not value:
        raise AssertionError(label)
    names.append(label)


def main():
    names = []
    contract, invocation = load(HERE / "contract.json"), load(RUN / "invocation.json")
    observation, closure = load(RUN / "observation.json"), load(RUN / "closure.json")
    check((contract["case_id"], contract["variant_id"], contract["version"])
          == ("K04", "K04.var03", "1.0.0-candidate"), "frozen diagnostic identity", names)
    dep = contract["dependency"]
    for label, path, key in (
        ("parent SXI", PARENT_RUN / "model.sxi", "sxi_sha256"),
        ("parent closure", PARENT_RUN / "closure.json", "closure_sha256"),
        ("parent signoff", PARENT / "cli-scope-signoff-2026-10-04.md", "signoff_sha256"),
        ("parent main source", PARENT / "main-input.json", "main_input_sha256"),
        ("parent accepted event", PARENT_RUN / "positive-model.log", "positive_event_sha256"),
        ("parent accepted report", PARENT_RUN / "positive-report-raw.json", "positive_report_sha256"),
    ):
        check(sha(path) == dep[key], label + " fingerprint", names)
    check(sha(RUN / "model.sxi") == dep["sxi_sha256"] == invocation["model_sxi_sha256"],
          "copied native SXI byte-identical to accepted parent", names)
    check(closure["error"] is None and closure["run_id"] == invocation["run_id"]
          == observation["run_id"] == contract["run_id"], "closed diagnostic run", names)
    check(sha(RUN / "invocation.json") == closure["invocation_sha256"],
          "invocation SHA seal", names)
    check(len(closure["raw"]) == 5, "five raw diagnostic files sealed", names)
    for name, seal in closure["raw"].items():
        path = RUN / name
        check(path.is_file() and path.stat().st_size == seal["bytes"]
              and sha(path) == seal["sha256"], "raw seal " + name, names)
    check(set(closure["raw"]) == {"model.sxi", "model.sxo", "run.log", "observation.json",
                                 f"${observation['child_pid']}@model.sxi$"},
          "exact raw diagnostic file names", names)
    check(closure["source_hashes_before"] == closure["source_hashes_after"]
          == invocation["source_hashes_before"], "source hashes stable during native run", names)
    check(closure["source_hashes_before"]["contract"] == sha(HERE / "contract.json")
          and sha(HERE / "contract.json") in
          (HERE / "run_native_ssh.ps1").read_text(encoding="utf-8"),
          "literal contract SHA preflight", names)
    check(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"]
          and invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue"
          and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1,
          "guarded SSH and protected GUI", names)
    original = "mdb=Microsoft Access Driver (*.mdb)|"
    temporary = "mdb=Microsoft Access Driver (*.mdb, *.accdb)|"
    check(invocation["association_before"] == observation["association_after"]
          == closure["association_after"] == original
          and invocation["association_during"] == temporary,
          "MDB association restored", names)
    check(invocation["working_directory"] == str(PARENT_RUN)
          and invocation["model_directory"] == str(RUN)
          and invocation["existing_working_directory_file"] == str(PARENT_RUN / "level1.mdb")
          and invocation["missing_file"] == str(RUN / "level1.mdb")
          and (PARENT_RUN / "level1.mdb").is_file()
          and not (RUN / "level1.mdb").exists(),
          "only new SXI directory lacks level1 MDB", names)
    check(invocation["arguments"].split('"')[1] == str(RUN / "model.sxi")
          and '-silent -threads 1 -calc' in invocation["arguments"],
          "exact CLI calculation target", names)
    shots = observation["timed_snapshots"]
    check(len(shots) == 2 and [s["label"] for s in shots]
          == ["after_20_seconds_or_exit", "after_45_seconds_or_exit"],
          "two ordered watchdog snapshots", names)
    check(invocation["watchdog_ms"] == contract["watchdog_ms"] == [20000, 25000],
          "frozen 20+25-second waits", names)
    check((stamp(shots[0]["observed_utc"]) - stamp(invocation["created_utc"])).total_seconds() >= 20
          and (stamp(shots[1]["observed_utc"]) - stamp(shots[0]["observed_utc"])).total_seconds() >= 25,
          "elapsed watchdog intervals observed", names)
    for shot in shots:
        check(shot["child_pid"] == observation["child_pid"]
              and shot["child_alive"] and shot["child_name"] == "Simlox.exe"
              and shot["child_session_id"] == 0
              and str(RUN / "model.sxi") in shot["child_command_line"],
              shot["label"] + " same live session-0 child", names)
        check(shot["files"]["model.sxi"] > 100000
              and shot["files"]["model.sxo"] == 4
              and shot["files"]["model.log"] is None
              and shot["files"]["run.log"] > 0,
              shot["label"] + " incomplete native output", names)
    check(shots[0]["files"] == shots[1]["files"]
          and shots[0]["child_cpu_seconds"] == shots[1]["child_cpu_seconds"],
          "no file or CPU progress during second interval", names)
    check(observation["outcome"] == closure["outcome"] == "watchdog_terminated_after_45_seconds"
          and observation["watchdog_stopped_only_verified_child"]
          and observation["exit_code"] == -1
          and observation["final_snapshot"]["child_alive"] is False
          and observation["gui_preserved"] and observation["error"] is None,
          "targeted watchdog termination with protected GUI", names)
    check((RUN / "model.sxo").stat().st_size == 4 and not (RUN / "model.log").exists(),
          "no usable simulation output", names)
    log = (RUN / "run.log").read_text(encoding="utf-8-sig")
    path = str(RUN / "level1.mdb").replace("\\", "/")
    check(path in log and "Converting input data" in log
          and "Input conversion completed" not in log
          and "Data successfully included" not in log,
          "native log stops at missing SXI-directory include", names)
    result = {"schema": "simlox-k04-var03-missing-mdb-author-validation/v1",
              "status": "PASS_DIAGNOSTIC_ONLY", "checks": len(names),
              "run_id": contract["run_id"], "closure_sha256": sha(RUN / "closure.json"),
              "sxi_sha256": sha(RUN / "model.sxi"),
              "run_log_sha256": sha(RUN / "run.log"),
              "outcome": observation["outcome"], "check_names": names}
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
