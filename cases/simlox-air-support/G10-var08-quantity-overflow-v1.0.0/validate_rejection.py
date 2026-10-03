"""Author replay of the sealed G10.var08 quantity-overflow rejection."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re

from build import HERE, PARENT, PARENT_SHA, build
from check_roundtrip import parse_native, populated

RUN_ID = "g10-var08-qty-overflow-v100-ssh-20261003-01"
RUN = HERE / "runs" / RUN_ID
OUT = HERE / "review" / "author-rejection-validation-2026-10-03.json"
RAW = {"input.json", "model.sxi", "model.sxo", "roundtrip-raw.json", "import.log", "export.log", "run.log", "steps.json", "roundtrip-validation.json"}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rows(doc: dict, name: str) -> list[dict]:
    table = next(t for t in doc["model"]["tables"] if t["name"] == name)
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, row, strict=True)) for inst in table["instances"] for row in inst["rows"]]


def main() -> None:
    checks: list[dict] = []

    def ck(name: str, actual: object, expected: object) -> None:
        checks.append({"name": name, "passed": actual == expected, "actual": actual, "expected": expected})

    parent, child = read(PARENT), read(HERE / "native-input.json")
    contract, diff = read(HERE / "contract.json"), read(HERE / "exact-diff.json")
    ck("parent source pin", sha(PARENT), PARENT_SHA)
    ck("parent signoff pin", sha(PARENT.parent / "cli-scope-signoff-2026-10-03.md"), contract["parent"]["signoff_sha256"])
    ck("parent native closure pin", sha(PARENT.parent / "runs" / contract["parent"]["native_run_id"] / "closure.json"), contract["parent"]["native_closure_sha256"])
    ck("input pin", sha(HERE / "native-input.json"), contract["native_input_sha256"])
    ck("builder identity", build(), child)
    ck("diff pin", sha(HERE / "exact-diff.json"), contract["exact_diff_sha256"])
    ck("diff source pins", (diff["parent_sha256"], diff["child_sha256"]), (PARENT_SHA, contract["native_input_sha256"]))
    before = {t["name"]: t for t in parent["model"]["tables"]}
    after = {t["name"]: t for t in child["model"]["tables"]}
    ck("same table names", set(after), set(before))
    ck("exact changed tables", sorted(n for n in before if before[n] != after[n]), ["ProblemDescription", "RedundancyLink"])
    ck("23 populated tables", len(populated(child)), 23)
    ck("source quantity boundary", [(r["IID"], r["QTYPL"]) for r in rows(child, "RedundancyLink")], [("TEACH-LRU-01", 2), ("TEACH-AUX-01", 1)])
    ck("installed LRU quantity", [(r["IID"], r["QTYPM"]) for r in rows(child, "ItemStructure") if r["IID"] == "TEACH-LRU-01" and r["MID"] == "TEACH-AIR-01"], [("TEACH-LRU-01", 2)])
    ck("redundancy links", [(r["NRL"], r["NRLRQ"], r["ACPA"]) for r in rows(child, "Redundancy")], [(2, 1, "ACTIVE")])
    ck("4 exceeds 2", diff["invalid_total_lru"] > diff["installed_lru_qtypm"], True)

    inv, closure, steps = (read(RUN / name) for name in ("invocation.json", "closure.json", "steps.json"))
    ck("run identity", (inv["case_id"], inv["variant_id"], inv["run_id"]), ("G10", "G10.var08", RUN_ID))
    ck("session-0 SSH", (inv["session_id"], inv["ssh_connection_present"], "sshd.exe" in [n.lower() for n in inv["ssh_ancestor_names"]]), (0, True, True))
    ck("GUI and mutex", (inv["gui"]["pid"], inv["gui"]["session_id"], inv["queue_mutex"]), (13340, 1, "Global\\SimloxIssue18NativeQueue"))
    ck("no runner error", closure["error"], None)
    ck("source stable", closure["source_hashes_before"], closure["source_hashes_after"])
    ck("invocation sealed", closure["invocation_sha256"], sha(RUN / "invocation.json"))
    ck("source hashes bound", inv["source_hashes_before"], closure["source_hashes_before"])
    source_paths = {"input": HERE / "native-input.json", "parent": PARENT, "parent_signoff": PARENT.parent / "cli-scope-signoff-2026-10-03.md", "parent_closure": PARENT.parent / "runs" / contract["parent"]["native_run_id"] / "closure.json", "manual": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"), "dictionary": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"), "contract": HERE / "contract.json", "builder": HERE / "build.py", "exact_diff": HERE / "exact-diff.json", "diff_checker": HERE / "describe_diff.py", "checker": HERE / "check_roundtrip.py", "runner_script": HERE / "run_native_ssh.ps1", "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"), "simlox_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")}
    for key, path in source_paths.items():
        ck(f"source {key}", inv["source_hashes_before"][key], sha(path))
    ck("raw set", set(closure["raw"]), RAW)
    for name, seal in closure["raw"].items():
        path = RUN / name
        ck(f"raw seal {name}", (sha(path), path.stat().st_size), (seal["sha256"], seal["bytes"]))
    ck("steps", [(s["name"], s["status"], s["exit_code"], s["gui_preserved"]) for s in steps], [("import", "completed", 0, True), ("export", "completed", 0, True), ("calc", "calc_observed", 0, True), ("check_import_export", "completed", 0, True)])
    ck("copied input", sha(RUN / "input.json"), contract["native_input_sha256"])
    rt = read(RUN / "roundtrip-validation.json")
    ck("roundtrip identity", (rt["passed"], rt["differences"], len(rt["populated_tables"])), (True, [], 23))
    exported = populated(parse_native(RUN / "roundtrip-raw.json"))
    ck("all business rows", {name: exported.get(name) for name in populated(child)}, populated(child))
    ck("import completion", "Import completed!" in (RUN / "import.log").read_text(encoding="utf-8-sig", errors="replace"), True)
    ck("export completion", "Export completed!" in (RUN / "export.log").read_text(encoding="utf-8-sig", errors="replace"), True)
    log = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    marker = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", log)
    ck("converter counts", marker.groups() if marker else None, ("1", "1", "0"))
    ck("specific error", re.findall(r"\(error #(\d+)\)", log), ["283"])
    ck("reviewed warning", re.findall(r"\(warning #(\d+)\)", log), ["108"])
    ck("error ties LRU quantity to system", bool(re.search(r"\(error #283\) Total number of the item in redundancies exceeds the number of available in the system: TEACH-LRU-01", log)), True)
    ck("invalid SXO", (RUN / "model.sxo").stat().st_size, 4)
    ck("no event log", (RUN / "model.log").exists(), False)
    ck("no JSON report", (RUN / "report-raw.json").exists(), False)
    failed = [c for c in checks if not c["passed"]]
    result = {"schema": "simlox-g10-var08-v100-author-rejection/v1", "passed": not failed, "checks_passed": len(checks) - len(failed), "checks_total": len(checks), "failures": failed, "run_id": RUN_ID, "native_error": 283, "decision": "bounded_converter_rejection_if_passed", "scope": "one_LRU_QTYPL2_times_NRL2_exceeds_QTYPM2", "publication_state": "not_published"}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "checks_passed": result["checks_passed"], "checks_total": result["checks_total"], "failures": failed[:5]}))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
