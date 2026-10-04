"""Read-only author replay for K04.var02 relative top-level MDB include."""
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE / "runs" / "k04-var02-relative-cwd-v104-ssh-20261004-01"
PARENT = HERE.parent / "K04-var01-nested-mdb-include-v1.0.0"
PARENT_RUN = PARENT / "runs" / "k04-var01-nested-mdb-v100-ssh-20261004-01"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native_json(path):
    raw = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        out = []
        quoted = escaped = False
        for i, char in enumerate(raw):
            if quoted:
                out.append(char)
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    quoted = False
            elif char == '"':
                quoted = True
                out.append(char)
            elif char == "," and raw[i + 1:].lstrip().startswith(("]", "}")):
                continue
            else:
                out.append(char)
        return json.loads("".join(out))


def tables(doc):
    result = {table["name"]: table for table in doc["model"]["tables"]}
    assert len(result) == len(doc["model"]["tables"])
    return result


def check(value, label, checks):
    if not value:
        raise AssertionError(label)
    checks.append(label)


def main():
    checks = []
    contract, closure = load(HERE / "contract.json"), load(RUN / "closure.json")
    invocation, steps = load(RUN / "invocation.json"), load(RUN / "steps.json")
    check((contract["case_id"], contract["variant_id"], contract["version"])
          == ("K04", "K04.var02", "1.0.4-candidate"), "frozen case contract", checks)
    dep = contract["dependency"]
    for name, key in (("main-input.json", "main_input_sha256"),
                      ("level1-source.json", "level1_source_sha256"),
                      ("level2-source.json", "level2_source_sha256")):
        check(sha(PARENT / name) == dep[key], f"accepted parent {name}", checks)
    check(sha(PARENT_RUN / "closure.json") == dep["closure_sha256"]
          and sha(PARENT / "cli-scope-signoff-2026-10-04.md") == dep["signoff_sha256"],
          "accepted parent closure and signoff", checks)
    for name, key in (("main-input.json", "main"), ("level1-source.json", "level1_source"),
                      ("level2-source.json", "level2_source")):
        check(sha(HERE / name) == sha(RUN / name) == contract["inputs_sha256"][key],
              f"frozen copied source {name}", checks)
    check(closure["error"] is None and closure["run_id"] == invocation["run_id"] == contract["run_id"],
          "closed native run without error", checks)
    check(sha(RUN / "invocation.json") == closure["invocation_sha256"], "invocation sealed", checks)
    check(len(closure["raw"]) >= 20, "complete raw file set", checks)
    for name, seal in closure["raw"].items():
        path = RUN / name
        check(path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"],
              f"raw seal {name}", checks)
    check(closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"],
          "source hashes unchanged during run", checks)
    check(closure["source_hashes_before"]["contract"] == sha(HERE / "contract.json")
          and sha(HERE / "contract.json") in (HERE / "run_native_ssh.ps1").read_text(encoding="utf-8"),
          "literal contract SHA preflight", checks)
    check(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"]
          and invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue"
          and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1,
          "guarded SSH and preserved GUI", checks)
    original = "mdb=Microsoft Access Driver (*.mdb)|"
    temporary = "mdb=Microsoft Access Driver (*.mdb, *.accdb)|"
    check(invocation["database_association_before"] == closure["database_association_after"] == original
          and invocation["database_association_during_calc"] == temporary,
          "MDB association restored", checks)
    expected_steps = ["level2_create", "level1_create", "main_import", "main_export",
                      "positive_calc", "positive_jsonreport", "alternate_calc", "alternate_jsonreport"]
    check([s["name"] for s in steps] == expected_steps
          and all(s["exit_code"] == 0 and s["status"] == "completed" and s["gui_preserved"] for s in steps),
          "eight guarded steps completed", checks)
    check(invocation["first_working_directory"] == str(RUN)
          and invocation["alternate_working_directory"] == contract["negative_working_directory"]
          and invocation["first_working_directory"] != invocation["alternate_working_directory"]
          and steps[4]["working_directory"] == str(RUN)
          and steps[6]["working_directory"] == contract["negative_working_directory"],
          "distinct process working directories", checks)
    check(not (Path(contract["negative_working_directory"]) / "level1.mdb").exists(),
          "alternate directory lacks level1 MDB", checks)
    check(steps[4]["arguments"].split('"')[1] == steps[6]["arguments"].split('"')[1] == str(RUN / "model.sxi")
          and closure["sxi_sha256"] == sha(RUN / "model.sxi"),
          "one unchanged SXI path and bytes", checks)
    level1_source, level2_source = load(HERE / "level1-source.json"), load(HERE / "level2-source.json")
    level1, level2 = load(RUN / "level1.readback.json"), load(RUN / "level2.readback.json")
    check(level1["process_bitness"] == level2["process_bitness"] == 32
          and level1["tables"] == ["IncludeFiles"] and level2["tables"] == ["Station"],
          "one user table in each MDB", checks)
    check(level1["rows"] == [{"INCFN": str(RUN / "level2.mdb"), "INCCO": "Required base station", "NOTE": None}]
          and level2["rows"] == [{"STID": "BASE-01", "DESCR": "Teaching base", "QTY": 1, "TYPE": "WS"}],
          "exact nested pointer and Station readback", checks)
    for name, readback in (("level1", level1), ("level2", level2)):
        path = RUN / f"{name}.mdb"
        check(readback["database_sha256"] == sha(path) and readback["database_bytes"] == path.stat().st_size,
              f"{name} MDB readback seal", checks)
    check(level1_source == {"table": "IncludeFiles", "columns": ["INCFN", "INCCO", "NOTE"],
                            "rows": [[str(RUN / "level2.mdb"), "Required base station", None]]}
          and level2_source == load(PARENT / "level2-source.json"),
          "frozen source chain", checks)
    check((RUN / "model.sxi").stat().st_size > 100000
          and (RUN / "positive-model.sxo").stat().st_size > 100000
          and (RUN / "alternate-model.sxo").stat().st_size > 100000,
          "usable SXI and both SXOs", checks)
    parent = tables(load(PARENT / "main-input.json"))
    source = tables(load(HERE / "main-input.json"))
    exported = tables(native_json(RUN / "main-roundtrip-raw.json"))
    check(len(parent) == len(source) == len(exported) == 32, "32 main model tables", checks)
    for name in sorted(parent.keys() - {"IncludeFiles"}):
        check(source[name] == parent[name], f"unchanged parent table {name}", checks)
    check(source["IncludeFiles"]["columns"] == parent["IncludeFiles"]["columns"]
          and source["IncludeFiles"]["instances"][0]["rows"]
          == [["level1.mdb", "Relative level1 at calculation working directory", None]],
          "sole relative top-level include", checks)
    for name, authored in source.items():
        observed = exported[name]
        if name == "IncludeFiles":
            check([{k: v for k, v in col.items() if k != "key"} for col in authored["columns"]]
                  == observed["columns"], "native IncludeFiles columns", checks)
        else:
            check(authored["columns"] == observed["columns"], f"native columns {name}", checks)
        if name == "Station":
            check(len(observed["instances"]) == 2
                  and observed["instances"][0]["instance_name"] == ""
                  and observed["instances"][0]["rows"] == [[None] * len(authored["columns"])]
                  and observed["instances"][1:] == authored["instances"],
                  "Station empty default plus authored AUX", checks)
        elif all(not instance["rows"] for instance in authored["instances"]):
            check(len(authored["instances"]) == len(observed["instances"])
                  and all(old["instance_name"] == new["instance_name"]
                          and new["rows"] in ([], [[None] * len(authored["columns"])] )
                          for old, new in zip(authored["instances"], observed["instances"])),
                  f"native empty placeholder {name}", checks)
        else:
            check(authored["instances"] == observed["instances"], f"native rows {name}", checks)
    path1 = str(RUN / "level1.mdb").replace("\\", "/")
    path2 = str(RUN / "level2.mdb").replace("\\", "/")
    for arm in ("positive", "alternate"):
        log = (RUN / f"{arm}-run.log").read_text(encoding="utf-8-sig")
        check(log.index(path1) < log.index("IncludeFiles, 1 record inserted")
              < log.index(path2) < log.index("Station, 1 record inserted")
              and log.count("Data successfully included") == 2,
              f"{arm} nested path resolution and traversal", checks)
        check("Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in log
              and re.findall(r"\(warning #(\d+)\)", log) == ["108", "126"]
              and not re.search(r"\((?:error|notice) #", log),
              f"{arm} zero converter errors and reviewed warnings", checks)
        check(sha(RUN / f"{arm}-model.log") == sha(PARENT_RUN / "model.log"),
              f"{arm} event log byte-identical to K04.var01", checks)
        check(sha(RUN / f"{arm}-report-raw.json") == sha(PARENT_RUN / "report-raw.json"),
              f"{arm} JSON report byte-identical to K04.var01", checks)
    result = {"schema": "simlox-k04-var02-relative-cwd-author-validation/v1", "status": "PASS",
              "checks": len(checks), "run_id": contract["run_id"],
              "closure_sha256": sha(RUN / "closure.json"),
              "level1_mdb_sha256": sha(RUN / "level1.mdb"),
              "level2_mdb_sha256": sha(RUN / "level2.mdb"),
              "event_log_sha256": sha(RUN / "positive-model.log"),
              "report_sha256": sha(RUN / "positive-report-raw.json"), "check_names": checks}
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
