"""Author read-only replay of D07.var04's native converter rejection."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from build import HERE, PARENT, PARENT_SHA, build
from check_roundtrip import parse_native, populated

RUN_ID = "d07-var04-child-frt-v100-ssh-20261003-01"
RUN = HERE / "runs" / RUN_ID
OUT = HERE / "review" / "author-rejection-validation-2026-10-03.json"
RAW = {"input.json", "model.sxi", "model.sxo", "roundtrip-raw.json", "import.log", "export.log", "run.log", "steps.json", "roundtrip-validation.json"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def row_maps(doc: dict, name: str) -> list[dict]:
    table = next(t for t in doc["model"]["tables"] if t["name"] == name)
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, row, strict=True)) for inst in table["instances"] for row in inst["rows"]]


def main() -> None:
    checks: list[dict] = []

    def ck(name: str, actual: object, expected: object) -> None:
        checks.append({"name": name, "passed": actual == expected, "actual": actual, "expected": expected})

    parent, child = read(PARENT), read(HERE / "native-input.json")
    contract, diff = read(HERE / "contract.json"), read(HERE / "parent-diff.json")
    ck("parent input pin", sha(PARENT), PARENT_SHA)
    ck("parent signoff pin", sha(PARENT.parent / "cli-scope-signoff-2026-10-03.md"), contract["parent"]["signoff_sha256"])
    ck("parent closure pin", sha(PARENT.parent / "runs" / contract["parent"]["native_run_id"] / "closure.json"), contract["parent"]["native_closure_sha256"])
    ck("child input pin", sha(HERE / "native-input.json"), contract["native_input_sha256"])
    ck("builder identity", build(), child)
    ck("diff pin", sha(HERE / "parent-diff.json"), contract["exact_diff_sha256"])
    ck("diff case identity", (diff["parent_case"], diff["child_case"]), ("D07.var02", "D07.var04"))
    ck("diff table keys", (sorted(diff["changed_tables"]), diff["added_tables"], diff["removed_tables"]), (["ItemFailureRate", "ProblemDescription"], {}, {}))
    before = {t["name"]: t for t in parent["model"]["tables"]}
    after = {t["name"]: t for t in child["model"]["tables"]}
    ck("same authored tables", set(after), set(before))
    ck("exact changed tables", sorted(n for n in before if before[n] != after[n]), ["ItemFailureRate", "ProblemDescription"])
    ck("21 populated tables", len(populated(child)), 21)
    ck("child KM rate", [(r["IID"], r["OPID"], r["FRT"]) for r in row_maps(child, "ItemFailureRate")], [("TEACH-LRU-01", "KM", 10000.0)])
    ck("mother KM rate", [(r["SID"], r["OPID"], r["FRT"]) for r in row_maps(child, "SystemFailureRate")], [("TEACH-AIR-01", "KM", 5000.0)])
    ck("one installed child", [(r["IID"], r["MID"], r["QTYPM"]) for r in row_maps(child, "ItemStructure")], [("TEACH-LRU-01", "TEACH-AIR-01", 1)])

    inv, closure, steps = (read(RUN / name) for name in ("invocation.json", "closure.json", "steps.json"))
    ck("run identity", (inv["case_id"], inv["variant_id"], inv["run_id"]), ("D07", "D07.var04", RUN_ID))
    ck("session-0 SSH", (inv["session_id"], inv["ssh_connection_present"], "sshd.exe" in [n.lower() for n in inv["ssh_ancestor_names"]]), (0, True, True))
    ck("GUI and mutex", (inv["gui"]["pid"], inv["gui"]["session_id"], inv["queue_mutex"]), (13340, 1, "Global\\SimloxIssue18NativeQueue"))
    ck("no runner error", closure["error"], None)
    ck("source stable", closure["source_hashes_before"], closure["source_hashes_after"])
    ck("invocation seal", closure["invocation_sha256"], sha(RUN / "invocation.json"))
    ck("invocation source seal", inv["source_hashes_before"], closure["source_hashes_before"])
    source_paths = {
        "input": HERE / "native-input.json", "parent": PARENT,
        "parent_signoff": PARENT.parent / "cli-scope-signoff-2026-10-03.md",
        "parent_closure": PARENT.parent / "runs" / contract["parent"]["native_run_id"] / "closure.json",
        "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
        "dictionary": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
        "contract": HERE / "contract.json", "builder": HERE / "build.py",
        "exact_diff": HERE / "parent-diff.json", "diff_checker": HERE / "describe_diff.py",
        "checker": HERE / "check_roundtrip.py", "runner_script": HERE / "run_native_ssh.ps1",
        "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
        "simlox_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
    }
    for key, path in source_paths.items():
        ck(f"source {key}", inv["source_hashes_before"][key], sha(path))
    ck("raw file set", set(closure["raw"]), RAW)
    for name, seal in closure["raw"].items():
        path = RUN / name
        ck(f"raw seal {name}", (sha(path), path.stat().st_size), (seal["sha256"], seal["bytes"]))
    ck("steps", [(s["name"], s["status"], s["exit_code"], s["gui_preserved"]) for s in steps], [("import", "completed", 0, True), ("export", "completed", 0, True), ("calc", "calc_observed", 0, True), ("check_import_export", "completed", 0, True)])
    ck("copied input", sha(RUN / "input.json"), contract["native_input_sha256"])
    roundtrip = read(RUN / "roundtrip-validation.json")
    ck("21-table roundtrip", (roundtrip["passed"], roundtrip["differences"], len(roundtrip["populated_tables"])), (True, [], 21))
    exported = populated(parse_native(RUN / "roundtrip-raw.json"))
    ck("all authored rows", {name: exported.get(name) for name in populated(child)}, populated(child))
    ck("import marker", "Import completed!" in (RUN / "import.log").read_text(encoding="utf-8-sig", errors="replace"), True)
    ck("export marker", "Export completed!" in (RUN / "export.log").read_text(encoding="utf-8-sig", errors="replace"), True)
    log = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    marker = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", log)
    ck("converter counts", marker.groups() if marker else None, ("1", "1", "0"))
    ck("specific error code", re.findall(r"\(error #(\d+)\)", log), ["2041"])
    ck("specific failure-rate relation", bool(re.search(r"\(error #2041\) The sum of item failure rates exceeds failure rate of system: TEACH-AIR-01 \(KM\)", log)), True)
    ck("reviewed warning", re.findall(r"\(warning #(\d+)\)", log), ["108"])
    ck("no simulation start", "Starting simulation" in log, False)
    ck("invalid SXO", (RUN / "model.sxo").stat().st_size, 4)
    ck("no event log", (RUN / "model.log").exists(), False)
    ck("no JSON report", (RUN / "report-raw.json").exists(), False)
    failed = [c for c in checks if not c["passed"]]
    result = {
        "schema": "simlox-d07-var04-v100-author-rejection/v1", "passed": not failed,
        "checks_passed": len(checks) - len(failed), "checks_total": len(checks), "failures": failed,
        "run_id": RUN_ID, "native_error": 2041,
        "decision": "bounded_converter_rejection_if_passed",
        "scope": "one installed item KM10000 exceeds mother system KM5000 while OPHOURS remains matched",
        "publication_state": "not_published",
    }
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps({"passed": result["passed"], "checks_passed": result["checks_passed"], "checks_total": result["checks_total"], "failures": failed[:5]}))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
