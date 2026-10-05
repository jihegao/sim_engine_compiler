"""Read-only E05.var01 v1.0.2 source, native and task-linked ledger replay."""

from __future__ import annotations

from collections import Counter
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PARENT = ROOT / "E05-local-repair-reissue-v1.0.0"
PARENT_RUN = PARENT / "runs" / "e05-v100-ssh-20260929-01"
SHARED = ROOT / "tools" / "validate_native.py"
NATIVE_BINDING = ROOT / "tools" / "native_binding.py"
sys.path.insert(0, str(ROOT / "tools"))
import validate_native as shared  # noqa: E402
import ledger_replay  # noqa: E402

INPUT_SHA = "5d91b1315d1a3d6321285492e8fcd4a3afd61bc8420347713f5646c31cfe5d08"
RUN_ID = "e05-var01-repair-backorder-v102-ssh-20261005-01"
RAW = {
    "input.json", "import.log", "model.sxi", "roundtrip-raw.json", "export.log",
    "roundtrip-check.json", "run.log", "model.sxo", "model.log",
    "report-raw.json", "report-export.log", "steps.json", "outcome.json",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def validate(run: Path) -> dict:
    failures: list[str] = []
    count = 0

    def ck(label: str, ok: bool) -> None:
        nonlocal count
        count += 1
        if not ok:
            failures.append(label)

    contract = load(HERE / "contract.json")
    ck("frozen contract identity", contract["case_id"] == "E05"
       and contract["variant_id"] == "E05.var01" and contract["version"] == "1.0.2"
       and contract["run_id"] == RUN_ID and contract["native_input_sha256"] == INPUT_SHA)
    ck("frozen validator", contract["author_validator_sha256"] == sha(Path(__file__))
       and contract["ledger_replay_sha256"] == sha(HERE / "ledger_replay.py")
       and contract["shared_validator_module_sha256"] == sha(SHARED)
       and contract["native_binding_module_sha256"] == sha(NATIVE_BINDING))
    ck("frozen child input", sha(HERE / "native-input.json") == INPUT_SHA)
    ck("accepted parent", sha(PARENT / "native-input.json") == contract["parent"]["input_sha256"]
       and sha(PARENT / "cli-scope-signoff-2026-09-29.md") == contract["parent"]["signoff_sha256"]
       and sha(PARENT_RUN / "closure.json") == contract["parent"]["closure_sha256"])
    parent_closure = load(PARENT_RUN / "closure.json")
    ck("parent raw set", len(parent_closure["raw"]) == 12)
    for name, record in parent_closure["raw"].items():
        path = PARENT_RUN / name
        ck(f"parent raw {name}", path.stat().st_size == record["bytes"] and sha(path) == record["sha256"])
    ck("run path and input", run.name == RUN_ID and sha(run / "input.json") == INPUT_SHA)
    invocation, closure, outcome = (load(run / name) for name in ("invocation.json", "closure.json", "outcome.json"))
    ck("run and closure identities", invocation["run_id"] == closure["run_id"] == RUN_ID
       and invocation["schema"] == "simlox-e05-var01-v102-invocation/ssh-cli-v1"
       and closure["schema"] == "simlox-e05-var01-v102-closure/v1")
    ck("SSH and protected GUI", invocation["session_id"] == 0
       and "sshd.exe" in invocation["ssh_ancestor_names"]
       and invocation["gui"] == {"pid": 13340, "session_id": 1,
                                 "start_utc": "2026-09-28T10:09:56.8261381Z"}
       and invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue")
    ck("invocation seal", closure["invocation_sha256"] == sha(run / "invocation.json"))
    ck("source hashes stable", invocation["source_hashes_before"] == closure["source_hashes_before"]
       == closure["source_hashes_after"])
    sources = {
        "contract": HERE / "contract.json", "input": HERE / "native-input.json",
        "builder": HERE / "build.py", "source_checker": HERE / "check_source.py",
        "roundtrip_checker": HERE / "check_roundtrip.py",
        "author_validator": HERE / "validate_native.py",
        "ledger_replay": HERE / "ledger_replay.py",
        "shared_validator_module": SHARED,
        "native_binding_module": NATIVE_BINDING,
        "parent_input": PARENT / "native-input.json",
        "parent_signoff": PARENT / "cli-scope-signoff-2026-09-29.md",
        "parent_closure": PARENT_RUN / "closure.json",
        "runner": HERE / "run_native_ssh.ps1",
    }
    for name, path in sources.items():
        ck(f"bound {name}", invocation["source_hashes_before"].get(name) == sha(path))
    ck("completed native closure", closure["error"] is None and outcome["error"] is None
       and outcome["roundtrip"] == "exact" and outcome["result"] == "native_run_completed")
    ck("raw file set", set(closure["raw"]) == RAW)
    for name, record in closure["raw"].items():
        path = run / name
        ck(f"raw {name}", path.stat().st_size == record["bytes"] and sha(path) == record["sha256"])
    steps = load(run / "steps.json")
    ck("native step order", [step["name"] for step in steps] == ["import", "export", "calc", "report"])
    for step in steps:
        ck(f"native step {step['name']}", step["status"] == "completed"
           and step["exit_code"] == 0 and step["gui_preserved"] is True)
    roundtrip = load(run / "roundtrip-check.json")
    ck("20-table roundtrip before calc", roundtrip["passed"] is True
       and roundtrip["differences"] == [] and len(roundtrip["populated_tables"]) == 20
       and shared.compare_roundtrip(run / "input.json", run / "roundtrip-raw.json")["all_equal"]
       and steps[1]["completed_utc"] < steps[2]["started_utc"])
    conversion_log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    conversion = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", conversion_log)
    ck("clean converter and interpreted warning", conversion is not None
       and tuple(map(int, conversion.groups())) == (0, 1, 0)
       and Counter(re.findall(r"\(warning #(\d+)\)", conversion_log)) == Counter({"108": 1}))
    ck("valid SXO", (run / "model.sxo").stat().st_size > 1000)

    raw_report = (run / "report-raw.json").read_bytes()
    report = json.loads(shared.remove_trailing_commas(raw_report))
    report_tables = report["report"]["tables"]
    for name in ("SystemResults", "StockTotalResults"):
        ck(f"one {name} table", sum(table["name"] == name for table in report_tables) == 1)
    tables = {table["name"]: table for table in report_tables}
    rows = {}
    for name in ("SystemResults", "StockTotalResults"):
        table = tables[name]
        columns = [column["name"] for column in table["columns"]]
        ck(f"{name} one instance", len(table["instances"]) == 1)
        rows[name] = [dict(zip(columns, row)) for row in table["instances"][0]["rows"]]
        ck(f"{name} 72 bins", len(rows[name]) == 72)
    ledger = ledger_replay.audit((run / "model.log").read_text(encoding="utf-8-sig", errors="replace"),
                                 rows["SystemResults"], rows["StockTotalResults"])
    count += ledger["checks"]
    failures.extend(ledger["failures"])
    ck("accepted E05 no-backorder control", "Backorder added" not in
       (PARENT_RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace"))
    return {"schema": "simlox-e05-var01-v102-author-replay/v1", "passed": not failures,
            "checks": count, "failures": failures, "run_id": run.name,
            "ledger": {key: value for key, value in ledger.items()
                       if key not in ("checks", "failures", "passed")},
            "scope": "one fixed-seed E05.var01 CLI boundary only"}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run", type=Path)
    args = parser.parse_args()
    try:
        verdict = validate(args.run)
    except (AssertionError, OSError, ValueError, KeyError, TypeError, IndexError, json.JSONDecodeError) as exc:
        verdict = {"schema": "simlox-e05-var01-v102-author-replay/v1", "passed": False,
                   "failures": [f"replay error: {type(exc).__name__}: {exc}"], "run_id": args.run.name}
    print(json.dumps(verdict, ensure_ascii=False, indent=2))
    return 0 if verdict["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
