"""Author replay of the sealed reversed replacement converter rejection."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from build import HERE, INPUT, PARENT, PARENT_SHA, build
from check_roundtrip import parse_native, populated

RUN_ID = "b05-var04-reversed-20260930-01"
RUN = HERE / "runs" / RUN_ID
INPUT_SHA = "e6cf31fc76ebc68b273aded864c39b12f2e69458be0c139f5944e5fb3f24e376"
EXE_SHA = "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"
OUT = HERE / "review" / "author-rejection-validation-2026-09-30.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> None:
    checks: list[dict] = []

    def ck(name: str, actual: object, expected: object) -> None:
        checks.append({"name": name, "actual": actual, "expected": expected, "passed": actual == expected})

    parent, child, contract, diff = (read(p) for p in (PARENT, INPUT, HERE / "contract.json", HERE / "exact-diff.json"))
    ck("parent SHA", sha(PARENT), PARENT_SHA)
    ck("child SHA", sha(INPUT), INPUT_SHA)
    ck("builder identity", build(), child)
    ck("contract parent", contract["parent_input_sha256"], PARENT_SHA)
    ck("diff binding", (diff["parent_sha256"], diff["input_sha256"]), (PARENT_SHA, INPUT_SHA))
    before = {t["name"]: t for t in parent["model"]["tables"]}
    after = {t["name"]: t for t in child["model"]["tables"]}
    ck("table set", set(after), set(before))
    ck("changed tables", sorted(n for n in before if before[n] != after[n]), ["ProblemDescription", "TaskBreakDown"])
    ck("20 populated tables", len(populated(child)), 20)
    breakdown = after["TaskBreakDown"]
    fields = [c["name"] for c in breakdown["columns"]]
    rows = [dict(zip(fields, r)) for r in breakdown["instances"][0]["rows"]]
    ck("reversed sequence", [(r["SEQ"], r["SUTID"], r["DURN"]) for r in rows],
       [(1, "<REPLACE>", 1 / 3), (2, "<REMOVE>", 1 / 6)])
    ck("positive E01 source available", (PARENT.parent / "runs" / "e01-v100-ssh-20260929-01" / "report-raw.json").is_file(), True)

    inv, closure, steps = (read(RUN / n) for n in ("invocation.json", "closure.json", "steps.json"))
    ck("run identity", (inv["case_id"], inv["run_id"], inv["variant"]), ("B05.var04", RUN_ID, "reversed-replacement"))
    ck("session-0 SSH", (inv["session_id"], inv["ssh_connection_present"], "sshd.exe" in [n.lower() for n in inv["ssh_ancestor_names"]]), (0, True, True))
    ck("GUI and mutex", (inv["gui"]["pid"], inv["gui"]["session_id"], inv["queue_mutex"]),
       (13340, 1, r"Global\SimloxIssue18NativeQueue"))
    ck("source hashes stable", closure["source_hashes_before"], closure["source_hashes_after"])
    source = closure["source_hashes_before"]
    ck("source closure", tuple(source[k] for k in ("input", "parent", "contract", "builder", "checker", "runner_script", "simlox_exe")),
       (INPUT_SHA, PARENT_SHA, sha(HERE / "contract.json"), sha(HERE / "build.py"), sha(HERE / "check_roundtrip.py"), sha(HERE / "run_native_ssh.ps1"), EXE_SHA))
    ck("invocation seal", closure["invocation_sha256"], sha(RUN / "invocation.json"))
    ck("no runner error", closure["error"], None)
    ck("guarded steps", [(s["name"], s["status"], s["exit_code"], s["gui_preserved"]) for s in steps],
       [("import", "completed", 0, True), ("export", "completed", 0, True),
        ("calc", "expected_rejection", 0, True), ("check_import_export", "completed", 0, True)])
    for name, info in closure["raw"].items():
        path = RUN / name
        ck(f"raw seal {name}", (sha(path), path.stat().st_size), (info["sha256"], info["bytes"]))
    ck("copied input", sha(RUN / "input.json"), INPUT_SHA)
    rt = read(RUN / "roundtrip-validation.json")
    ck("roundtrip checker", (rt["passed"], rt["source_sha256"], len(rt["populated_tables"])), (True, INPUT_SHA, 20))
    exported_rows, source_rows = populated(parse_native(RUN / "roundtrip-raw.json")), populated(child)
    ck("source rows after export", {n: exported_rows.get(n) for n in source_rows}, source_rows)
    ck("import marker", "Import completed!" in (RUN / "import.log").read_text(encoding="utf-8-sig", errors="replace"), True)
    ck("export marker", "Export completed!" in (RUN / "export.log").read_text(encoding="utf-8-sig", errors="replace"), True)
    log = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    conversion = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", log)
    ck("conversion counts", conversion.groups() if conversion else None, ("1", "1", "0"))
    ck("exact error codes", re.findall(r"error #(\d+)", log), ["163"])
    ck("exact warning codes", re.findall(r"warning #(\d+)", log), ["108"])
    ck("error text", "Invalid subtask breakdown of sub replacement task: E01-SURP" in log, True)
    ck("no valid simulation output", (RUN / "model.sxo").stat().st_size <= 4, True)
    ck("no JSON report", (RUN / "report-raw.json").exists(), False)
    failed = [c for c in checks if not c["passed"]]
    result = {"schema": "simlox-b05-var04-replacement-order-author-replay/v1", "passed": not failed,
              "passed_count": len(checks) - len(failed), "failed_count": len(failed), "failed": failed,
              "run_id": RUN_ID, "native_error": 163,
              "checks": [{"name": c["name"], "passed": c["passed"]} for c in checks],
              "decision": "bounded_converter_rejection_if_passed",
              "limits": ["One installed executable and one reversed local replacement input.",
                         "No simulation or report behavior is accepted from this rejected model.",
                         "GUI visuals and cross-engine behavior remain unverified."]}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "passed_count": result["passed_count"],
                      "failed_count": result["failed_count"], "failed": failed[:5]}))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
