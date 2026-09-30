"""Author replay of the sealed A14.var07 native converter rejection."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from build import HERE, PARENT, PARENT_SHA, build
from check_roundtrip import parse_native, populated

RUN_ID = "a14-var07-leaf-two-v100-20261001-01"
RUN = HERE / "runs" / RUN_ID
INPUT = HERE / "native-input.json"
INPUT_SHA = "0cf06efc8fc50f1ac2771e904dd7dd84dc503e4ee1a72b8fc1ce47e9e15c77cf"
EXE_SHA = "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"
OUT = HERE / "review" / "author-rejection-validation-2026-10-01.json"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def rows(doc: dict, name: str) -> list[dict]:
    table, = (t for t in doc["model"]["tables"] if t["name"] == name)
    names = [c["name"] for c in table["columns"]]
    return [dict(zip(names, row, strict=True)) for row in table["instances"][0]["rows"]]


def main() -> None:
    checks: list[dict] = []

    def ck(name: str, actual: object, expected: object) -> None:
        checks.append({"name": name, "actual": actual, "expected": expected,
                       "passed": actual == expected})

    parent, child = read(PARENT), read(INPUT)
    contract, diff = read(HERE / "contract.json"), read(HERE / "exact-diff.json")
    ck("parent SHA", sha(PARENT), PARENT_SHA)
    ck("child SHA", sha(INPUT), INPUT_SHA)
    ck("builder identity", build(), child)
    ck("contract binding", (contract["parent"]["input_sha256"], contract["native_input_sha256"],
                            contract["exact_diff_sha256"]),
       (PARENT_SHA, INPUT_SHA, sha(HERE / "exact-diff.json")))
    ck("diff binding", (diff["parent_sha256"], diff["input_sha256"]), (PARENT_SHA, INPUT_SHA))
    before = {t["name"]: t for t in parent["model"]["tables"]}
    after = {t["name"]: t for t in child["model"]["tables"]}
    ck("table set", set(after), set(before))
    ck("changed tables", sorted(n for n in before if before[n] != after[n]),
       ["OperationProfile", "ProblemDescription"])
    ck("dependence profile unchanged", after["MissionDependenceProfile"],
       before["MissionDependenceProfile"])
    ck("exact changed table values", diff["changed_tables"],
       {n: {"before": before[n], "after": after[n]}
        for n in ("ProblemDescription", "OperationProfile")})
    ck("one business cell delta", diff["operation_profile_cell_delta"], [[2, "IQTY", 1, 2]])
    child_op = rows(child, "OperationProfile")
    ck("EXECUTE target", [(r["PRID"], r["SPRID"], r["STIM"], r["IQTY"])
                          for r in child_op if r["SPRID"] == "EXECUTE"],
       [("A14-WAVE", "EXECUTE", 8.0, 2)])
    ck("14 populated source tables", len(populated(child)), 14)

    inv, closure, steps = (read(RUN / n) for n in
                           ("invocation.json", "closure.json", "steps.json"))
    ck("run identity", (inv["run_id"], inv["variant"]), (RUN_ID, "leaf-iqty-two"))
    ck("session-0 SSH", (inv["session_id"], inv["ssh_connection_present"],
                          "sshd.exe" in [n.lower() for n in inv["ssh_ancestor_names"]]),
       (0, True, True))
    ck("GUI and mutex", (inv["gui"]["pid"], inv["gui"]["session_id"], inv["queue_mutex"]),
       (13340, 1, "Global\\SimloxIssue18NativeQueue"))
    ck("source hashes stable", closure["source_hashes_before"], closure["source_hashes_after"])
    source = closure["source_hashes_before"]
    ck("source closure", tuple(source[k] for k in
       ("input", "parent", "contract", "builder", "exact_diff", "diff_checker",
        "checker", "runner_script", "simlox_exe")),
       (INPUT_SHA, PARENT_SHA, sha(HERE / "contract.json"), sha(HERE / "build.py"),
        sha(HERE / "exact-diff.json"), sha(HERE / "describe_diff.py"),
        sha(HERE / "check_roundtrip.py"), sha(HERE / "run_native_ssh.ps1"), EXE_SHA))
    ck("invocation seal", closure["invocation_sha256"], sha(RUN / "invocation.json"))
    ck("no runner error", closure["error"], None)
    ck("runner scope", closure["scope"], "ambiguous_leaf_converter_probe")
    ck("guarded steps", [(s["name"], s["status"], s["exit_code"], s["gui_preserved"])
                          for s in steps],
       [("import", "completed", 0, True), ("export", "completed", 0, True),
        ("calc", "calc_observed", 0, True),
        ("check_import_export", "completed", 0, True)])
    for name, info in closure["raw"].items():
        path = RUN / name
        ck(f"raw seal {name}", (sha(path), path.stat().st_size),
           (info["sha256"], info["bytes"]))
    ck("copied input", sha(RUN / "input.json"), INPUT_SHA)
    rt = read(RUN / "roundtrip-validation.json")
    ck("roundtrip checker", (rt["passed"], rt["source_sha256"],
                             len(rt["populated_tables"])), (True, INPUT_SHA, 14))
    exported_rows = populated(parse_native(RUN / "roundtrip-raw.json"))
    source_rows = populated(child)
    ck("source rows after export", {n: exported_rows.get(n) for n in source_rows}, source_rows)
    ck("import marker", "Import completed!" in (RUN / "import.log").read_text(
       encoding="utf-8-sig", errors="replace"), True)
    ck("export marker", "Export completed!" in (RUN / "export.log").read_text(
       encoding="utf-8-sig", errors="replace"), True)
    log = (RUN / "run.log").read_text(encoding="utf-8-sig", errors="replace")
    conversion = re.search(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", log)
    ck("conversion counts", conversion.groups() if conversion else None, ("1", "2", "0"))
    ck("error code", re.findall(r"error #(\d+)", log), ["514"])
    ck("warning codes", sorted(re.findall(r"warning #(\d+)", log)), ["108", "126"])
    ck("error table and text", "Form: MissionDependenceProfile\nrec 1: (error #514) Dependent mission with IQTY>1 for this profile: PRID: A14-WAVE, DMTID: EXECUTE" in log.replace("\r\n", "\n"), True)
    ck("no valid simulation output", (RUN / "model.sxo").stat().st_size, 4)
    ck("no JSON report", (RUN / "report-raw.json").exists(), False)

    failed = [c for c in checks if not c["passed"]]
    result = {"schema": "simlox-a14-var07-leaf-iqty-two-author-replay/v1",
              "passed": not failed, "passed_count": len(checks)-len(failed),
              "failed_count": len(failed), "failed": failed,
              "run_id": RUN_ID, "native_error": 514,
              "checks": [{"name": c["name"], "passed": c["passed"]} for c in checks],
              "decision": "bounded_converter_rejection_if_passed",
              "limits": ["One installed executable and one two-wave IQTY=2 EXECUTE leaf.",
                         "No simulation/report behavior is accepted from this rejected model.",
                         "GUI visuals and cross-engine behavior remain unverified."]}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "passed_count": result["passed_count"],
                      "failed_count": result["failed_count"], "failed": failed[:5]}))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
