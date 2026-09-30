"""Read-only author replay of paired unfinished-horizon converter rejections."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from check_roundtrip import parse_native, populated

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "A13-start-dependence-v1.0.0" / "dependent-input.json"
VARIANTS = ("unfinished-control", "unfinished-dependency")
RUNS = {v: HERE / "runs" / f"a13-var04-{v}-v102-20261001-01" for v in VARIANTS}
OUT = HERE / "review" / "author-validation-2026-10-01.json"
CONTRACT_SHA = "a572cc1786d0c630ee47d302ea1f37b89e30f3e6066c3f5fedebc7560eea30bf"
DIFF_SHA = "4b77e8da05b4a6eed522fada0e3678708a6ad878141d9a846e42d126df21a009"
PARENT_SHA = "954e40c17ba0f34f041c405076195fa2d1ac8b471d65e7de4b441e51fa8a5246"
EXE_SHA = "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def table(doc: dict, name: str) -> dict:
    found = [t for t in doc["model"]["tables"] if t["name"] == name]
    assert len(found) == 1, name
    return found[0]


def main() -> None:
    checks: list[dict] = []

    def ck(name: str, condition: bool) -> None:
        checks.append({"name": name, "passed": bool(condition)})

    contract, diff = read(HERE / "contract.json"), read(HERE / "exact-diff.json")
    ck("contract freeze", sha(HERE / "contract.json") == CONTRACT_SHA)
    ck("parent source", sha(PARENT) == PARENT_SHA == contract["parent"]["input_sha256"])
    ck("exact diff freeze", sha(HERE / "exact-diff.json") == DIFF_SHA == contract["exact_diff_sha256"])
    ck("installed manual", sha(Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")) == contract["source"]["manual_sha256"])
    ck("installed dictionary", sha(Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")) == contract["source"]["dictionary_sha256"])
    parent = read(PARENT)
    sources: dict[str, dict] = {}
    for variant in VARIANTS:
        path = HERE / f"{variant}-input.json"
        ck(f"{variant} input freeze", sha(path) == contract["inputs_sha256"][variant])
        doc = read(path)
        sources[variant] = doc
        p_tables = {t["name"]: t for t in parent["model"]["tables"]}
        c_tables = {t["name"]: t for t in doc["model"]["tables"]}
        changed = {name: {"before": p_tables[name]["instances"], "after": tab["instances"]}
                   for name, tab in c_tables.items() if tab != p_tables[name]}
        ck(f"{variant} exact parent delta", changed == diff["variants"][variant]["changed_tables"])
        ctrl = table(doc, "Control")
        ctrl_names = [c["name"] for c in ctrl["columns"]]
        ctrl_row, = ctrl["instances"][0]["rows"]
        ck(f"{variant} stop and half-hour", (ctrl_row[ctrl_names.index("SIMPE")],
           ctrl_row[ctrl_names.index("RCEND")], ctrl_row[ctrl_names.index("RCINT")]) == (11, 11, .5))
        rc = table(doc, "ResultCollection")
        rc_names = [c["name"] for c in rc["columns"]]
        rc_rows = rc["instances"][0]["rows"]
        ck(f"{variant} explicit report windows", {r[rc_names.index("RTYPE")] for r in rc_rows} ==
           {"MISSION", "SYSTEM"} and all(r[rc_names.index("RCEND")] == 11 for r in rc_rows))
    left = {t["name"]: t for t in sources[VARIANTS[0]]["model"]["tables"]}
    right = {t["name"]: t for t in sources[VARIANTS[1]]["model"]["tables"]}
    ck("paired source only label and START row", {n for n in left if left[n] != right[n]} ==
       {"ProblemDescription", "MissionDependence"})

    for variant, run in RUNS.items():
        inv, closure, steps = (read(run / name) for name in ("invocation.json", "closure.json", "steps.json"))
        ck(f"{variant} run identity", inv["run_id"] == closure["run_id"] == run.name and inv["variant"] == variant)
        ck(f"{variant} SSH session", inv["session_id"] == 0 and inv["ssh_connection_present"]
           and "sshd.exe" in [n.lower() for n in inv["ssh_ancestor_names"]])
        ck(f"{variant} GUI mutex", inv["gui"]["pid"] == 13340 and inv["gui"]["session_id"] == 1
           and inv["queue_mutex"] == "Global\\SimloxIssue18NativeQueue")
        ck(f"{variant} invocation seal", sha(run / "invocation.json") == closure["invocation_sha256"])
        ck(f"{variant} closure no runner error", closure["error"] is None and closure["scope"] ==
           "start_dependency_unfinished_precedent")
        hashes = closure["source_hashes_before"]
        ck(f"{variant} stable source", hashes == closure["source_hashes_after"])
        ck(f"{variant} pinned source and exe", (hashes["input"], hashes["parent"], hashes["contract"],
           hashes["exact_diff"], hashes["simlox_exe"]) ==
           (contract["inputs_sha256"][variant], PARENT_SHA, CONTRACT_SHA, DIFF_SHA, EXE_SHA))
        for key, name in (("builder", "build.py"), ("diff_checker", "describe_diff.py"),
                          ("checker", "check_roundtrip.py"), ("runner_script", "run_native_ssh.ps1")):
            ck(f"{variant} {key} seal", hashes[key] == sha(HERE / name))
        ck(f"{variant} ordered steps", [s["name"] for s in steps] ==
           ["import", "export", "calc", "check_import_export"])
        ck(f"{variant} guarded steps", all(s["exit_code"] == 0 and s["gui_preserved"]
           and s["status"] == ("calc_observed" if s["name"] == "calc" else "completed") for s in steps))
        ck(f"{variant} raw file set", set(closure["raw"]) == {p.name for p in run.iterdir() if p.is_file()} -
           {"invocation.json", "closure.json"})
        for name, item in closure["raw"].items():
            path = run / name
            ck(f"{variant} raw {name}", path.stat().st_size == item["bytes"] and sha(path) == item["sha256"])
        ck(f"{variant} copied input", sha(run / "input.json") == contract["inputs_sha256"][variant])
        rt = read(run / "roundtrip-validation.json")
        count = 13 if variant.endswith("control") else 14
        before = populated(sources[variant])
        after = populated(parse_native(run / "roundtrip-raw.json"))
        ck(f"{variant} exact roundtrip", rt["passed"] and not rt["differences"] and
           len(before) == len(rt["populated_tables"]) == count and
           all(after.get(name) == rows for name, rows in before.items()))
        log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        ck(f"{variant} exact converter count", re.findall(r"Input conversion completed\. Errors: (\d+), Warnings: (\d+), Notes: (\d+)", log) ==
           [("1", "2", "0")])
        ck(f"{variant} exact #204", re.findall(r"error #(\d+)", log) == ["204"] and
           "Form: Operations" in log and "Some missions may not return before simulation period ends" in log)
        ck(f"{variant} expected warnings", sorted(re.findall(r"warning #(\d+)", log)) == ["108", "126"])
        ck(f"{variant} invalid SXO", (run / "model.sxo").stat().st_size == 4)
        ck(f"{variant} no behavior outputs", not (run / "model.log").exists() and
           not (run / "report-raw.json").exists())
    failed = [c for c in checks if not c["passed"]]
    result = {"schema": "simlox-a13-var04-unfinished-v102-author-validation/v1",
              "passed": not failed, "check_count": len(checks), "passed_count": len(checks)-len(failed),
              "failed_count": len(failed), "failures": failed,
              "run_ids": {v: r.name for v, r in RUNS.items()},
              "decision": "bounded_converter_204_go_if_passed",
              "limits": ["No simulation behavior or report accepted.",
                         "One premature stop with scheduled fixed missions; no universal unfinished-mission rule."]}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    print(json.dumps({"passed": result["passed"], "checks": len(checks), "failed": failed[:8]}))
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
