"""Replay the bounded strategy-switch converter rejection from sealed raw bytes."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUN = HERE / "runs/i07-var09-time-to-stock-v101-ssh-20261005-01"
OLD = ROOT / "I07-var09-strategy-switch-v1.0.0"
OLD_RUN = OLD / "runs/i07-var09-time-to-stock-v100-ssh-20261005-02"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def tables(path: Path) -> dict:
    document = read(path)
    return {table["name"]: table for table in document["model"]["tables"]}


def main() -> int:
    failed: list[str] = []
    count = 0

    def check(label: str, passed: bool) -> None:
        nonlocal count
        count += 1
        if not passed:
            failed.append(label)

    contract, invocation, closure, outcome, steps = (
        read(path) for path in (
            HERE / "contract.json", RUN / "invocation.json", RUN / "closure.json",
            RUN / "outcome.json", RUN / "steps.json"
        )
    )
    old_index = read(OLD / "evidence-index.json")
    old_closure = read(OLD_RUN / "closure.json")
    check("identity", contract["case_id"] == "I07" and contract["variant_id"] == "I07.var09"
          and contract["version"] == "1.0.1-candidate" and contract["run_id"] == invocation["run_id"] == closure["run_id"] == RUN.name)
    check("old diagnostic pins", sha(OLD / "evidence-index.json") == contract["excluded_parent"]["evidence_index_sha256"]
          and sha(OLD_RUN / "closure.json") == contract["excluded_parent"]["closure_sha256"]
          and sha(OLD / "native-input.json") == contract["excluded_parent"]["input_sha256"]
          and old_index["publication_state"] == "excluded_diagnostic" and old_closure["error"] is not None)
    for name, seal in old_closure["raw"].items():
        path = OLD_RUN / name
        check(f"old raw {name}", path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"])
    check("old raw count", len(old_closure["raw"]) == 10)
    source_map = {
        "contract": HERE / "contract.json", "input": HERE / "native-input.json",
        "builder": HERE / "build.py", "roundtrip_checker": HERE / "check_roundtrip.py",
        "parent_input": ROOT / "E15-var01-time-based-cycle-v1.0.0/native-input.json",
        "parent_event": ROOT / "E15-var01-time-based-cycle-v1.0.0/runs/e15-var01-timecycle-v100-ssh-20261005-01/model.log",
        "accepted_signoff": ROOT / "E15-var01-time-based-cycle-v1.0.1/cli-scope-signoff-2026-10-05.md",
        "accepted_index": ROOT / "E15-var01-time-based-cycle-v1.0.1/evidence-index.json",
        "old_index": OLD / "evidence-index.json", "old_closure": OLD_RUN / "closure.json",
        "old_input": OLD / "native-input.json",
        "exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
        "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
        "runner": HERE / "run_native_ssh.ps1",
        "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
    }
    check("source inventory", set(invocation["source_hashes_before"]) == set(source_map))
    for name, path in source_map.items():
        check(f"source {name}", sha(path) == invocation["source_hashes_before"][name]
              == closure["source_hashes_before"][name] == closure["source_hashes_after"][name])
    check("invocation/closure", closure["invocation_sha256"] == sha(RUN / "invocation.json")
          and closure["error"] is None and outcome["error"] is None)
    check("SSH/GUI/mutex", invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"]
          and invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue"
          and invocation["gui"] == {"pid": 13340, "session_id": 1, "start_utc": "2026-09-28T10:09:56.8261381Z"})
    check("three serial native steps", [step["name"] for step in steps] == ["import", "export", "calc"]
          and all(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"] for step in steps))
    check("raw count", len(closure["raw"]) == 10)
    for name, seal in closure["raw"].items():
        path = RUN / name
        check(f"new raw {name}", path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"])
    check("copied input", sha(RUN / "input.json") == contract["source"]["input_sha256"])
    old_tables, new_tables = tables(OLD / "native-input.json"), tables(HERE / "native-input.json")
    old_row = old_tables["ChangesItemReorder"]["instances"][0]["rows"][0]
    new_row = new_tables["ChangesItemReorder"]["instances"][0]["rows"][0]
    check("sole LEADT correction", old_row == ["TEACH-DU-01", "DEPOT-01", 5.0, None, None, None, 0.0, None]
          and new_row == ["TEACH-DU-01", "DEPOT-01", 5.0, 1.0, None, None, 0.0, None]
          and {k: v for k, v in old_tables.items() if k != "ChangesItemReorder"} == {k: v for k, v in new_tables.items() if k != "ChangesItemReorder"})
    exported = tables(RUN / "roundtrip-raw.json")
    populated = {name: table for name, table in new_tables.items() if any(instance["rows"] for instance in table["instances"])}
    roundtrip = read(RUN / "roundtrip-check.json")
    check("22 exact authored tables", len(populated) == 22 and roundtrip["passed"] is True and roundtrip["mismatches"] == []
          and all(exported[name]["columns"] == table["columns"] and exported[name]["instances"] == table["instances"] for name, table in populated.items()))
    log = (RUN / "run.log").read_text(encoding="utf-8-sig")
    check("sole strategy error", "Input conversion completed. Errors: 1, Warnings: 2, Notes: 0" in log
          and Counter(re.findall(r"\(error #(\d+)\)", log)) == Counter({"375": 1})
          and re.search(r"(?ms)Form: ChangesItemReorder\s+rec 1: \(error #375\) Inconsistent change of ROINT:\s+TEACH-DU-01/DEPOT-01", log) is not None)
    check("reviewed warnings", Counter(re.findall(r"\(warning #(\d+)\)", log)) == Counter({"108": 1, "376": 1}))
    check("invalid result/no event", (RUN / "model.sxo").stat().st_size == 4 and not (RUN / "model.log").exists()
          and outcome["result"] == "expected_converter_rejection")
    result = {"schema": "simlox-i07-var09-v101-author-replay/v1", "passed": not failed,
              "checks": count, "differences": failed, "publication_state": "not_published",
              "scope": "One converter rejection of ROINT16-to0 switch with unchanged LEADT1; no runtime behavior inferred."}
    (HERE / "author-validation-2026-10-05.json").write_bytes((json.dumps(result, indent=2) + "\n").encode())
    print(json.dumps(result))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, KeyError, TypeError, IndexError, AssertionError) as exc:
        print(json.dumps({"passed": False, "differences": [f"validator error: {type(exc).__name__}: {exc}"]}))
        sys.exit(1)
