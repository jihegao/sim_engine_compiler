"""Validate one sealed native K03 delimiter-text reimport against its parent."""
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE / "runs" / "k03-var01-reimport-v100-ssh-20261004-01"
PARENT = HERE.parent / "K03-var01-cli-text-export-v1.0.1"
PARENT_RUN = PARENT / "runs" / "k03-var01-text-v101-ssh-20261004-01"
K02_RUN = HERE.parent / "K02-var01-json-structure-v1.0.1" / "runs" / "k02-var01-named-v101-ssh-20261004-01"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def check(value, label, checks):
    if not value:
        raise AssertionError(label)
    checks.append(label)


def main():
    checks = []
    contract = load(HERE / "contract.json")
    closure = load(RUN / "closure.json")
    invocation = load(RUN / "invocation.json")
    steps = load(RUN / "steps.json")
    check(closure["error"] is None, "native closure has no error", checks)
    check(sha(RUN / "invocation.json") == closure["invocation_sha256"], "invocation sealed", checks)
    for name, seal in closure["raw"].items():
        path = RUN / name
        check(path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"], f"raw seal {name}", checks)
    check(closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"], "source hashes unchanged", checks)
    check(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"]
          and invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue"
          and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] > 0,
          "guarded SSH and preserved GUI", checks)
    check([s["name"] for s in steps] == ["timport", "jexport", "calc", "jsonreport"]
          and all(s["exit_code"] == 0 and s["status"] == "completed" and s["gui_preserved"] for s in steps),
          "four native steps completed", checks)
    check("-timport" in steps[0]["arguments"] and "-twidth 4096 -tsep !" in steps[0]["arguments"], "frozen import command", checks)
    check(sha(RUN / "input.txt") == contract["accepted_parent"]["text_sha256"] == sha(PARENT_RUN / "model.txt"), "accepted text source exact", checks)
    check((RUN / "text-import.log").stat().st_size == 0, "native import log empty", checks)
    check((RUN / "model.sxi").stat().st_size > 100000 and (RUN / "model.sxo").stat().st_size > 100000, "usable native SXI and SXO", checks)

    before = load(PARENT_RUN / "model-raw.json")["model"]["tables"]
    after = load(RUN / "roundtrip-raw.json")["model"]["tables"]
    check(len(before) == len(after) == 31, "31 tables", checks)
    changes = []
    cells = 0
    for left, right in zip(before, after):
        name = left["name"]
        check(name == right["name"] and left["columns"] == right["columns"], f"table and columns {name}", checks)
        check(len(left["instances"]) == len(right["instances"]), f"instance count {name}", checks)
        columns = [c["name"] for c in left["columns"]]
        for i, (l_instance, r_instance) in enumerate(zip(left["instances"], right["instances"])):
            check(l_instance["instance_name"] == r_instance["instance_name"], f"instance name {name}/{i}", checks)
            check(len(l_instance["rows"]) == len(r_instance["rows"]), f"row count {name}/{i}", checks)
            for row_index, (l_row, r_row) in enumerate(zip(l_instance["rows"], r_instance["rows"])):
                check(len(l_row) == len(r_row) == len(columns), f"row width {name}/{i}/{row_index}", checks)
                for col, old, new in zip(columns, l_row, r_row):
                    cells += 1
                    if old != new:
                        changes.append({"table": name, "instance": l_instance["instance_name"],
                                        "row": row_index, "column": col, "before": old, "after": new})
    expected = [{"table": "OperationProfile", "instance": "", "row": 0,
                 "column": "DTIM", "before": 0.3333333333333333, "after": 0.3}]
    check(changes == expected, "sole JSON cell change is observed DTIM precision loss", checks)
    check(cells == 381, "381 model cells compared", checks)

    log = (RUN / "run.log").read_text(encoding="utf-8-sig")
    check("Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in log
          and re.findall(r"\(warning #(\d+)\)", log) == ["108", "126"]
          and not re.search(r"\((?:error|notice) #", log), "zero converter errors and reviewed warnings", checks)
    check(sha(RUN / "model.log") == sha(K02_RUN / "model.log"), "native event log byte-identical to K02", checks)
    check(sha(RUN / "report-raw.json") == sha(K02_RUN / "report-raw.json"), "native raw report byte-identical to K02", checks)
    result = {"schema": "simlox-k03-var01-text-reimport-author-validation/v1",
              "status": "PASS", "checks": len(checks), "tables": len(after),
              "cells_compared": cells, "observed_changes": changes,
              "closure_sha256": sha(RUN / "closure.json"),
              "event_log_sha256": sha(RUN / "model.log"),
              "report_sha256": sha(RUN / "report-raw.json"),
              "check_names": checks}
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
