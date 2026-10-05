"""Author replay of the frozen below-nominal time-based ISTOH rejection."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PARENT = ROOT / "E15-var01-time-based-cycle-v1.0.1"
PARENT_SOURCE = ROOT / "E15-var01-time-based-cycle-v1.0.0"
PARENT_RUN = PARENT_SOURCE / "runs/e15-var01-timecycle-v100-ssh-20261005-01"
PARENT_REPORT = PARENT / "runs/e15-var01-timecycle-report-v101-ssh-20261005-01/selected-report-raw.json"
E02 = ROOT / "E02-zero-stock-local-backorder-v1.0.0"
RUN_ID = "e15-var09-istoh-below-v100-ssh-20261005-01"
RUN = HERE / "runs" / RUN_ID


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def populated(path: Path) -> dict:
    return {t["name"]: t for t in read(path)["model"]["tables"]
            if any(i["rows"] for i in t["instances"])}


def main() -> dict:
    failures: list[str] = []
    count = 0

    def ck(label: str, good: bool) -> None:
        nonlocal count
        count += 1
        if not good:
            failures.append(label)

    contract, inv, closure = [read(p) for p in (HERE / "contract.json", RUN / "invocation.json", RUN / "closure.json")]
    ck("identity", (contract["case_id"], contract["variant_id"], contract["version"], contract["run_id"]) ==
       ("E15", "E15.var09", "1.0.0-candidate", RUN_ID))
    ck("run and invocation", inv["run_id"] == closure["run_id"] == RUN_ID
       and closure["invocation_sha256"] == sha(RUN / "invocation.json"))
    ck("frozen sources", inv["source_hashes_before"] == closure["source_hashes_before"] == closure["source_hashes_after"])
    source = {
        "contract": HERE / "contract.json", "input": HERE / "native-input.json",
        "builder": HERE / "build.py", "roundtrip_checker": HERE / "check_roundtrip.py",
        "parent_input": PARENT_SOURCE / "native-input.json",
        "parent_signoff": PARENT / "cli-scope-signoff-2026-10-05.md",
        "parent_index": PARENT / "evidence-index.json", "parent_event": PARENT_RUN / "model.log",
        "parent_report": PARENT_REPORT,
        "e02_input": E02 / "native-input.json",
        "e02_signoff": E02 / "cli-scope-signoff-2026-09-29.md",
        "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
        "exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
        "runner": HERE / "run_native_ssh.ps1",
        "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
    }
    for name, path in source.items():
        ck(f"source {name}", sha(path) == inv["source_hashes_before"][name])
    ck("contract child pins", contract["source"]["input_sha256"] == sha(source["input"])
       and contract["source"]["builder_sha256"] == sha(source["builder"])
       and contract["source"]["roundtrip_checker_sha256"] == sha(source["roundtrip_checker"])
       and contract["source"]["manual_pdf_sha256"] == sha(source["manual"])
       and contract["source"]["simlox_exe_sha256"] == sha(source["exe"]))
    ck("accepted parent pins", all(contract["accepted_parent"][key] == sha(source[name]) for key, name in [
        ("input_sha256", "parent_input"), ("signoff_sha256", "parent_signoff"),
        ("evidence_index_sha256", "parent_index"), ("event_log_sha256", "parent_event"),
        ("selected_report_sha256", "parent_report")]))
    ck("E02 pins", contract["prerequisite_E02"]["input_sha256"] == sha(source["e02_input"])
       and contract["prerequisite_E02"]["signoff_sha256"] == sha(source["e02_signoff"]))
    ck("GUI and SSH guard", inv["session_id"] == 0 and "sshd.exe" in inv["ssh_ancestor_names"]
       and inv["queue_mutex"] == r"Global\SimloxIssue18NativeQueue"
       and inv["gui"] == {"pid": 13340, "session_id": 1, "start_utc": "2026-09-28T10:09:56.8261381Z"})
    steps = read(RUN / "steps.json")
    ck("three guarded stages", [x["name"] for x in steps] == ["import", "export", "calc_converter_gate"]
       and all(x["status"] == "completed" and x["exit_code"] == 0 and x["gui_preserved"] for x in steps))
    ck("raw set", set(closure["raw"]) == {"input.json", "model.sxi", "model.sxo", "import.log", "export.log",
       "roundtrip-raw.json", "roundtrip-check.json", "run.log", "steps.json", "outcome.json"})
    for name, seal in closure["raw"].items():
        path = RUN / name
        ck(f"raw {name}", path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"])
    ck("copied input", sha(RUN / "input.json") == sha(source["input"]))
    roundtrip = read(RUN / "roundtrip-check.json")
    authored, exported = populated(RUN / "input.json"), populated(RUN / "roundtrip-raw.json")
    ck("21 exact authored tables", roundtrip["passed"] and roundtrip["authored_populated_tables"] == 21
       and roundtrip["mismatches"] == [] and len(authored) == 21
       and all(exported.get(k) == v for k, v in authored.items()))

    parent_input, child_input = read(source["parent_input"]), read(source["input"])
    copy = json.loads(json.dumps(parent_input))
    pts, cts = parent_input["model"]["tables"], child_input["model"]["tables"]
    ck("31 table topology", len(pts) == len(cts) == 31 and [t["name"] for t in pts] == [t["name"] for t in cts])
    allocation = next(t for t in copy["model"]["tables"] if t["name"] == "StockAllocation")
    row = allocation["instances"][0]["rows"][1]
    ck("parent equality configuration", row[:7] == ["AIR_BASIC", "TEACH-DU-01", "DEPOT-01", 4, 2, None, None]
       and next(t for t in pts if t["name"] == "ItemReorder")["instances"][0]["rows"][0][5] == 16.0)
    row[6] = 3
    ck("sole ISTOH cell delta", copy == child_input)

    outcome = read(RUN / "outcome.json")
    log = (RUN / "run.log").read_text(encoding="utf-8-sig")
    ck("frozen negative outcome", outcome["import_export"] == "exact_roundtrip"
       and outcome["converter_summary"] == [1, 2, 0]
       and outcome["error_codes"] == ["377"] and outcome["expected_negative"] is True
       and outcome["error"] is None and closure["expected_negative"] is True and closure["error"] is None)
    ck("converter summary", "Input conversion completed. Errors: 1, Warnings: 2, Notes: 0" in log)
    ck("target error", re.findall(r"\(error #(\d+)\)", log) == ["377"]
       and "rec 2: (error #377) Initial stock on hand too small (ISTOH < STSIZ): TEACH-DU-01 / DEPOT-01" in log)
    ck("known warnings", re.findall(r"\(warning #(\d+)\)", log) == ["108", "376"]
       and "ROSIZ not used at location with time-based reorder strategy: TEACH-DU-01 / DEPOT-01" in log)
    ck("invalid result", (RUN / "model.sxo").stat().st_size == 4
       and not (RUN / "model.log").exists() and not (RUN / "selected-report-raw.json").exists())
    return {"schema": "simlox-e15-var09-v100-author-validation/v1", "passed": not failures,
            "checks": count, "differences": failures, "scope": "bounded_below_nominal_converter_rejection",
            "publication_state": "not_published"}


if __name__ == "__main__":
    try:
        result = main()
    except (OSError, ValueError, KeyError, TypeError, IndexError, AssertionError) as exc:
        result = {"passed": False, "differences": [f"validator error: {type(exc).__name__}: {exc}"]}
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result["passed"] else 1)
