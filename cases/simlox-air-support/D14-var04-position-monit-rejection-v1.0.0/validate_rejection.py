"""Replay the sealed D14.var04 native converter rejection without running SIMLOX."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from check_roundtrip import native_json, populated

HERE = Path(__file__).resolve().parent
RUN_ID = "d14-var04-position-monit-y-v100-ssh-20261002-01"
INPUT_SHA = "cda1509cdf704a92b374c3aed3b40b49ade2598189406368ad2b56e0564e5a03"
CONTRACT_SHA = "ae9bfac4ef1f38532ba41d01e4786bf4313373e46966e6f0572a103103198fa9"
DIFF_SHA = "83f09477630a0dc74b276780ecda30c852dceb6558dca122ad1687cd5e49f28c"
PARENT_SHA = "29dd9638ecaf5980b7ecf90ef41644afbbcca3a9b15f88dceb8f2fe3e5c32903"
PARENT_CLOSURE_SHA = "7a0977eefefb06be79860ad0982efa2f8c0d4259c8b0905e2a17a5fca9122ead"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    run = HERE / "runs" / RUN_ID
    errors: list[str] = []
    checks = 0

    def need(value: bool, label: str) -> None:
        nonlocal checks
        checks += 1
        if not value:
            errors.append(label)

    contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
    parent = HERE / contract["accepted_parent"]["package"]
    need(sha(HERE / "native-input.json") == INPUT_SHA, "input SHA")
    need(sha(HERE / "contract.json") == CONTRACT_SHA, "contract SHA")
    need(sha(HERE / "exact-diff.json") == DIFF_SHA, "diff SHA")
    need(sha(parent / "native-input-monitored.json") == PARENT_SHA, "parent input")
    need(sha(parent / "runs" / "d14-var01-monitored-v101-ssh-20261002-01" / "closure.json") == PARENT_CLOSURE_SHA, "parent closure")
    need(contract["input_sha256"] == INPUT_SHA and contract["exact_diff_sha256"] == DIFF_SHA, "contract pins")
    source = native_json(HERE / "native-input.json")
    table = {t["name"]: t for t in source["model"]["tables"]}
    row = table["MaterielPM"]["instances"][0]["rows"][0]
    names = [c["name"] for c in table["MaterielPM"]["columns"]]
    need(row[names.index("MID")] == "POS-A" and row[names.index("MONIT")] == "Y", "position MONIT source")
    diff = json.loads((HERE / "exact-diff.json").read_text(encoding="utf-8"))
    need(set(diff["changed"]) == {"MaterielPM", "ProblemDescription"}, "only model delta")
    invocation = json.loads((run / "invocation.json").read_text(encoding="utf-8-sig"))
    closure = json.loads((run / "closure.json").read_text(encoding="utf-8-sig"))
    steps = json.loads((run / "steps.json").read_text(encoding="utf-8-sig"))
    roundtrip = json.loads((run / "roundtrip-validation.json").read_text(encoding="utf-8-sig"))
    need(closure["error"] is None and closure["run_id"] == RUN_ID and closure["arm"] == "position-monit-y", "closure identity")
    need(sha(run / "invocation.json") == closure["invocation_sha256"], "invocation seal")
    need(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"], "SSH guard")
    need(invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue", "host mutex")
    need(invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] > 0, "GUI identity")
    need([s["name"] for s in steps] == ["import", "export", "calc", "check_import_export"], "step sequence")
    need([s["status"] for s in steps] == ["completed", "completed", "expected_rejection", "completed"], "step statuses")
    for step in steps:
        need(step["exit_code"] == 0 and step["gui_preserved"], f"{step['name']} process/GUI")
    for key, value in closure["source_hashes_before"].items():
        need(closure["source_hashes_after"][key] == value, f"source unchanged {key}")
    for key, expected in {"input": INPUT_SHA, "parent_y": PARENT_SHA,
                          "parent_y_closure": PARENT_CLOSURE_SHA, "contract": CONTRACT_SHA,
                          "exact_diff": DIFF_SHA}.items():
        need(closure["source_hashes_before"][key] == expected, f"runner pinned {key}")
    need(len(closure["raw"]) == 9, "nine raw records")
    for name, entry in closure["raw"].items():
        path = run / name
        need(path.is_file() and path.stat().st_size == entry["bytes"] and sha(path) == entry["sha256"], f"raw seal {name}")
    need(roundtrip["passed"] is True and roundtrip["differences"] == [], "roundtrip checker")
    need(len(roundtrip["populated_tables"]) == 20, "20 authored tables")
    before = populated(native_json(run / "input.json"))
    after = populated(native_json(run / "roundtrip-raw.json"))
    for name, body in before.items():
        need(after.get(name) == body, f"roundtrip {name}")
    log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    need(re.findall(r"\(error #(\d+)\)", log) == ["361"], "error #361 only")
    need("Form: MaterielPM" in log and "MONIT is not allowed for materiel positions:  POS-A" in log,
         "diagnostic attributes position MONIT")
    need("Input conversion completed. Errors: 1, Warnings: 1, Notes: 0" in log, "conversion count")
    need(re.findall(r"\(warning #(\d+)\)", log) == ["108"], "warning 108 only")
    need((run / "model.sxo").stat().st_size == 4 and not (run / "model.log").exists(), "no simulation output")
    verdict = {"schema": "simlox-d14-var04-author-rejection-replay/v1", "case_id": "D14",
               "variant_id": "D14.var04", "version": "1.0.0", "run_id": RUN_ID,
               "closure_sha256": sha(run / "closure.json"), "checks": checks,
               "passed_checks": checks - len(errors), "passed": not errors, "differences": errors,
               "scope": "exact native converter rejection of position-linked MONIT=Y; no valid simulation",
               "publication_state": "not_published"}
    print(json.dumps(verdict, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
