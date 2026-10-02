"""Replay the three sealed installed-CLI Prelife converter rejections."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from build import ARMS, HERE, PARENTS, make
from check_roundtrip import native_json, populated

RUN_IDS = {
    "two-blank-qty": "g11-var13-two-blank-qty-v100-ssh-20261003-01",
    "overallocated-qty": "g11-var13-overallocated-qty-v100-ssh-20261003-01",
    "missing-middle": "g11-var13-missing-middle-v100-ssh-20261003-01",
}
ERRORS = {
    "two-blank-qty": ("312", "more than one PrelifeData row with empty quantity"),
    "overallocated-qty": ("311", "Materiel quantity is less than the prelife quantity"),
    "missing-middle": ("414", "sub-prelife materiel is not part of the mother-prelife materiel"),
}
EXPECTED_CHANGED = {
    "two-blank-qty": ["PrelifeData", "ProblemDescription"],
    "overallocated-qty": ["PrelifeData", "ProblemDescription"],
    "missing-middle": ["Prelife", "PrelifeData", "PrelifeStructure", "ProblemDescription"],
}
OUT = HERE / "author-validation.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def tables(doc: dict) -> dict:
    return {t["name"]: t for t in doc["model"]["tables"]}


def main() -> None:
    checks: list[dict] = []

    def ck(arm: str, name: str, actual: object, expected: object) -> None:
        checks.append({"arm": arm, "name": name, "passed": actual == expected,
                       "actual": actual if actual != expected else None,
                       "expected": expected if actual != expected else None})

    contract, diff = read(HERE / "contract.json"), read(HERE / "exact-diff.json")
    ck("all", "contract identity", (contract["case_id"], contract["variant_id"]), ("G11", "G11.var13"))
    ck("all", "diff pin", sha(HERE / "exact-diff.json"), contract["exact_diff_sha256"])
    ck("all", "contract arm set", set(contract["arms"]), set(ARMS))
    ck("all", "diff arm set", set(diff["arms"]), set(ARMS))
    for arm in ARMS:
        run = HERE / "runs" / RUN_IDS[arm]
        pin = contract["arms"][arm]
        parent_path, parent_sha = PARENTS[arm]
        child_path = HERE / f"native-input-{arm}.json"
        parent, child = read(parent_path), read(child_path)
        ck(arm, "parent source pin", sha(parent_path), parent_sha)
        ck(arm, "parent contract pin", pin["accepted_parent"]["input_sha256"], parent_sha)
        ck(arm, "accepted parent native closure pin", sha(parent_path.parent / "runs" /
           ("g11-var04-explicit-control-v101-ssh-20261002-01" if arm == "missing-middle" else
            "g11-var05-remaining-blank-v100-ssh-20261003-01" if arm == "two-blank-qty" else
            "g11-var05-explicit-two-v100-ssh-20261003-01") / "closure.json"),
           pin["accepted_parent"]["native_closure_sha256"])
        ck(arm, "child source pin", sha(child_path), pin["input_sha256"])
        ck(arm, "builder result", make(arm), child)
        before, after = tables(parent), tables(child)
        changed = sorted(name for name in before if before[name] != after[name])
        ck(arm, "exact changed tables", changed, EXPECTED_CHANGED[arm])
        ck(arm, "exact diff binding", (diff["arms"][arm]["parent_sha256"],
           diff["arms"][arm]["input_sha256"], sorted(diff["arms"][arm]["changed"])),
           (parent_sha, pin["input_sha256"], EXPECTED_CHANGED[arm]))
        ck(arm, "exact diff before/after", diff["arms"][arm]["changed"],
           {name: {"before": before[name], "after": after[name]} for name in changed})

        invocation, closure, steps, rt = (read(run / name) for name in
                                          ("invocation.json", "closure.json", "steps.json", "roundtrip-validation.json"))
        ck(arm, "run and arm", (invocation["run_id"], invocation["arm"], closure["run_id"], closure["arm"]),
           (RUN_IDS[arm], arm, RUN_IDS[arm], arm))
        ck(arm, "session zero SSH", (invocation["session_id"], "sshd.exe" in
           [n.lower() for n in invocation["ssh_ancestor_names"]], invocation["execution_mode"]),
           (0, True, "session0_ssh_cli"))
        ck(arm, "GUI and queue", (invocation["gui"]["pid"], invocation["gui"]["session_id"],
           invocation["queue_mutex"]), (13340, 1, "Global\\SimloxIssue18NativeQueue"))
        ck(arm, "source unchanged", closure["source_hashes_after"], closure["source_hashes_before"])
        source = closure["source_hashes_before"]
        ck(arm, "source hashes", tuple(source[k] for k in
           ("input", "parent", "parent_closure", "contract", "exact_diff", "builder", "diff_builder",
            "checker", "runner", "exe", "manual", "dictionary")),
           (sha(child_path), sha(parent_path), pin["accepted_parent"]["native_closure_sha256"],
            sha(HERE / "contract.json"), sha(HERE / "exact-diff.json"), sha(HERE / "build.py"),
            sha(HERE / "describe_diff.py"), sha(HERE / "check_roundtrip.py"),
            sha(HERE / "run_native_ssh.ps1"),
            "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0",
            contract["source"]["manual_sha256"], contract["source"]["dictionary_sha256"]))
        ck(arm, "invocation seal", sha(run / "invocation.json"), closure["invocation_sha256"])
        for name, sealed in closure["raw"].items():
            path = run / name
            ck(arm, f"raw seal {name}", (sha(path), path.stat().st_size),
               (sealed["sha256"], sealed["bytes"]))
        ck(arm, "raw file set", set(closure["raw"]),
           {p.name for p in run.iterdir() if p.is_file()} - {"invocation.json", "closure.json"})
        ck(arm, "copied input", sha(run / "input.json"), pin["input_sha256"])
        exported, source_rows = populated(native_json(run / "roundtrip-raw.json")), populated(child)
        ck(arm, "row-preserving export", {n: exported.get(n) for n in source_rows}, source_rows)
        ck(arm, "roundtrip check", (rt["passed"], rt["differences"], rt["source_sha256"]),
           (True, [], pin["input_sha256"]))
        ck(arm, "guarded step status", [(s["name"], s["status"], s["exit_code"], s["gui_preserved"])
              for s in steps], [("import", "completed", 0, True), ("export", "completed", 0, True),
                               ("calc", "failed", 0, True), ("check_import_export", "completed", 0, True)])
        ck(arm, "calc wrapper reason", (steps[2]["error"], closure["error"]),
           ("calc output missing: model.sxo", "calc output missing: model.sxo"))
        ck(arm, "registry restored", (invocation["prelife_log_option_before"],
           closure["prelife_log_option_after"]), ("NO", "NO"))
        log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        expected_code, expected_text = ERRORS[arm]
        marker = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", log)
        ck(arm, "conversion counts", marker.groups() if marker else None,
           ("1", "1" if arm == "missing-middle" else "2", "0"))
        ck(arm, "exact converter error", re.findall(r"\(error #(\d+)\)", log), [expected_code])
        ck(arm, "boundary error text", expected_text in log, True)
        ck(arm, "exact converter warnings", re.findall(r"\(warning #(\d+)\)", log),
           ["108"] if arm == "missing-middle" else ["108", "126"])
        ck(arm, "invalid simulation output", (run / "model.sxo").stat().st_size, 4)
        ck(arm, "no JSON report", (run / "report-raw.json").exists(), False)
    failed = [c for c in checks if not c["passed"]]
    result = {"schema": "simlox-g11-var13-author-rejection-replay/v1", "case_id": "G11",
              "variant_id": "G11.var13", "passed": not failed,
              "passed_count": len(checks) - len(failed), "failed_count": len(failed),
              "checks": [{"arm": c["arm"], "name": c["name"], "passed": c["passed"]} for c in checks],
              "failed": failed, "native_error_codes": {a: ERRORS[a][0] for a in ARMS},
              "decision": "three_bounded_converter_rejections_if_passed",
              "limits": ["Single installed executable and three frozen negative inputs.",
                         "No simulation/report behavior accepted from the invalid models.",
                         "GUI visuals and cross-engine behavior unverified."]}
    OUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "passed_count": result["passed_count"],
                      "failed_count": result["failed_count"], "failed": failed[:3]}))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
