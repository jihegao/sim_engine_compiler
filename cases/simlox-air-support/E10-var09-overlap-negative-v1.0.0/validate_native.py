"""Author replay for the E10.var09 version-specific overlap rejection."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
from pathlib import Path
import re

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUN_ID = "e10-var09-overlap-v100-ssh-20261003-01"
CLOSURE_SHA = "5c78a68b6549e99f1eae3e9f3d0fcaff23529c726570acf51c398825d13356f4"
RAW_NAMES = {"input.json", "model.sxi", "roundtrip-raw.json", "import.log", "export.log", "model.sxo", "run.log", "steps.json", "roundtrip-validation.json"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> int:
    failures: list[str] = []
    checks = 0

    def ck(label: str, passed: bool) -> None:
        nonlocal checks
        checks += 1
        if not passed:
            failures.append(label)

    contract, diff = (read(HERE / name) for name in ("contract.json", "exact-diff.json"))
    parent = ROOT / contract["accepted_parent"]["package"]
    parent_run = parent / "runs" / contract["accepted_parent"]["run_id"]
    run = HERE / "runs" / RUN_ID
    ck("frozen contract/diff", contract["case_id"] == "E10" and contract["variant_id"] == "E10.var09" and contract["case_version"] == "1.0.0-candidate" and contract["exact_diff_sha256"] == sha(HERE / "exact-diff.json"))
    ck("accepted zero-error parent pins", sha(parent / "native-input.json") == contract["accepted_parent"]["input_sha256"] == diff["parent_sha256"] and sha(parent_run / "closure.json") == contract["accepted_parent"]["native_closure_sha256"] and sha(parent / "evidence-index.json") == contract["accepted_parent"]["evidence_index_sha256"] and "Input conversion completed. Errors: 0," in (parent_run / "run.log").read_text(encoding="utf-8-sig"))
    ck("child input seal", sha(HERE / "native-input.json") == contract["native_input_sha256"] == diff["source_sha256"])
    profiles = next(t for t in parse_native(HERE / "native-input.json")["model"]["tables"] if t["name"] == "TransportPolicyProfile")
    ck("exact overlap input rows", profiles["instances"][0]["rows"] == [["DOWN-POLICY", "ONDEM", 0.0, 1, 0.0, 12.0, 1, 2.0, None, None], ["DOWN-POLICY", "ONDEM", 11.0, 1, 0.0, 25.0, 1, 2.0, None, None]])
    ck("frozen negative closure", sha(run / "closure.json") == CLOSURE_SHA)
    inv, closure, steps = (read(run / name) for name in ("invocation.json", "closure.json", "steps.json"))
    ck("run identity", inv["case_id"] == "E10" and inv["variant_id"] == "E10.var09" and inv["run_id"] == closure["run_id"] == RUN_ID)
    ck("guarded SSH GUI queue", inv["execution_mode"] == "ssh_cli_v1" and inv["session_id"] == 0 and inv["ssh_connection_present"] is True and "sshd.exe" in inv["ssh_ancestor_names"] and inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue" and inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1)
    ck("stable source", closure["error"] is None and closure["invocation_sha256"] == sha(run / "invocation.json") and closure["source_hashes_before"] == closure["source_hashes_after"] == inv["source_hashes_before"])
    pins = inv["source_hashes_before"]
    ck("local source pins", all(pins[key] == sha(HERE / filename) for key, filename in (("input", "native-input.json"), ("contract", "contract.json"), ("exact_diff", "exact-diff.json"), ("builder", "build.py"), ("diff_builder", "describe_diff.py"), ("checker", "check_roundtrip.py"), ("runner_script", "run_native_ssh.ps1"))))
    ck("parent source pins", pins["parent"] == contract["accepted_parent"]["input_sha256"] and pins["parent_closure"] == contract["accepted_parent"]["native_closure_sha256"] and pins["parent_index"] == contract["accepted_parent"]["evidence_index_sha256"])
    ck("installed source pins", pins["simlox_exe"] == contract["source"]["simlox_exe_sha256"] and pins["manual"] == contract["source"]["manual_pdf_sha256"] and pins["dictionary"] == contract["source"]["dictionary_sha256"])
    ck("four guarded diagnostic steps", [step["name"] for step in steps] == ["import", "export", "calc", "check_import_export"] and all(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"] is True for step in steps))
    ck("raw artifact set", set(closure["raw"]) == RAW_NAMES)
    for name, meta in closure["raw"].items():
        path = run / name
        ck(f"raw {name}", path.is_file() and path.stat().st_size == meta["bytes"] and sha(path) == meta["sha256"])
    ck("copied child source", sha(run / "input.json") == contract["native_input_sha256"])
    before = populated(parse_native(run / "input.json"))
    after = populated(parse_native(run / "roundtrip-raw.json"))
    rt = read(run / "roundtrip-validation.json")
    ck("exact 22-table roundtrip", len(before) == 22 and rt["passed"] is True and rt["differences"] == [] and all(after.get(name) == table for name, table in before.items()))
    ck("import/export completion", "Import completed!" in (run / "import.log").read_text(encoding="utf-8-sig") and "Export completed!" in (run / "export.log").read_text(encoding="utf-8-sig"))
    log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    ck("converter counts", "Input conversion completed. Errors: 1, Warnings: 1, Notes: 0" in log and Counter(re.findall(r"\(warning #(\d+)\)", log)) == Counter({"108": 1}) and Counter(re.findall(r"\(error #(\d+)\)", log)) == Counter({"153": 1}))
    ck("source-bound policy rejection", re.search(r"Form: TransportPolicyProfile\s+rec 1: \(error #153\) FIX transports during ONDEM period in profile: DOWN-POLICY", log) is not None)
    ck("invalid SXO and absent report", (run / "model.sxo").stat().st_size == 4 and not (run / "report-raw.json").exists() and not (run / "model.log").exists())
    ck("no semantic simulation marker", "Starting simulation" not in log and "Saving results" not in log)
    result = {"schema": "simlox-e10-var09-overlap-negative-v100-author-validation/v1", "passed": not failures, "checks": checks, "differences": failures, "classification": "native_conversion_rejection_only" if not failures else "no_go", "publication_state": "not_published"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
