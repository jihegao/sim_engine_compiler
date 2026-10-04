"""Read-only author replay for K05.var05 Access runtime include."""
import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN = HERE / "runs" / "k05-var05-mdb-v102-ssh-20261004-01"
PARENT = HERE.parent / "K02-var01-json-structure-v1.0.1"
PARENT_RUN = PARENT / "runs" / "k02-var01-named-v101-ssh-20261004-01"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def native_json(path):
    raw = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # The installed SIMLOX exporter may leave a comma before ] or }.
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
    rows = doc["model"]["tables"]
    result = {table["name"]: table for table in rows}
    assert len(result) == len(rows)
    return result


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
    check(contract["case_id"] == "K05" and contract["variant_id"] == "K05.var05"
          and contract["version"] == "1.0.2-candidate", "frozen K05.var05 contract", checks)
    check(sha(PARENT / "named-input.json") == contract["dependency"]["input_sha256"]
          and sha(PARENT_RUN / "closure.json") == contract["dependency"]["closure_sha256"],
          "accepted K02 dependency fingerprints", checks)
    check(sha(HERE / "main-input.json") == sha(RUN / "main-input.json") == contract["inputs_sha256"]["main"]
          and sha(HERE / "database-source.json") == sha(RUN / "database-source.json") == contract["inputs_sha256"]["database_source"],
          "frozen sources copied into run", checks)
    check(closure["error"] is None and closure["run_id"] == invocation["run_id"] == contract["run_id"],
          "closed native run without error", checks)
    check(sha(RUN / "invocation.json") == closure["invocation_sha256"], "invocation sealed", checks)
    for name, seal in closure["raw"].items():
        path = RUN / name
        check(path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"], f"raw seal {name}", checks)
    check(closure["source_hashes_before"] == closure["source_hashes_after"] == invocation["source_hashes_before"],
          "source hashes unchanged during run", checks)
    check(invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"]
          and invocation["queue_mutex"] == "Global\\SimloxIssue18NativeQueue"
          and invocation["gui"]["pid"] == 13340 and invocation["gui"]["session_id"] == 1,
          "guarded SSH and preserved GUI", checks)
    original = "mdb=Microsoft Access Driver (*.mdb)|"
    temporary = "mdb=Microsoft Access Driver (*.mdb, *.accdb)|"
    check(invocation["database_association_before"] == closure["database_association_after"] == original
          and invocation["database_association_during_calc"] == temporary,
          "MDB ODBC association restored", checks)
    check([s["name"] for s in steps] == ["database_create", "main_import", "main_export", "calc", "jsonreport"]
          and all(s["exit_code"] == 0 and s["status"] == "completed" and s["gui_preserved"] for s in steps),
          "five native steps completed", checks)
    readback = load(RUN / "included.readback.json")
    db_source = load(HERE / "database-source.json")
    check(readback["process_bitness"] == 32 and readback["driver"] == "Microsoft Access Driver (*.mdb)"
          and readback["tables"] == ["Station"] and readback["rows"] == [dict(zip(db_source["columns"], db_source["rows"][0]))]
          and readback["database_sha256"] == sha(RUN / "included.mdb")
          and readback["database_bytes"] == (RUN / "included.mdb").stat().st_size,
          "task-local MDB row readback and hash", checks)
    check((RUN / "model.sxi").stat().st_size > 100000 and (RUN / "model.sxo").stat().st_size > 100000,
          "usable SXI and SXO", checks)
    parent = tables(load(PARENT / "named-input.json"))
    main_source = tables(load(HERE / "main-input.json"))
    main_native = tables(native_json(RUN / "main-roundtrip-raw.json"))
    check(set(main_source) == set(parent) | {"IncludeFiles"} == set(main_native), "32 expected model tables", checks)
    for name in parent:
        if name != "Station":
            check(main_source[name] == parent[name], f"unchanged source table {name}", checks)
    source_station = main_source["Station"]
    parent_station = parent["Station"]
    check(source_station["columns"] == parent_station["columns"]
          and source_station["instances"] == parent_station["instances"][1:]
          and db_source["rows"] == [parent_station["instances"][0]["rows"][0][:4]],
          "exact K02 Station row split", checks)
    check(main_source["IncludeFiles"]["instances"][0]["rows"]
          == [[str(RUN / "included.mdb"), "Required base station", None]],
          "sole absolute MDB include", checks)
    for name, source in main_source.items():
        exported = main_native[name]
        if name == "IncludeFiles":
            check([{k: v for k, v in col.items() if k != "key"} for col in source["columns"]]
                  == exported["columns"], "native IncludeFiles columns without inferred key metadata", checks)
        else:
            check(source["columns"] == exported["columns"], f"native columns {name}", checks)
        if name == "Station":
            extra = exported["instances"][:1]
            check(len(exported["instances"]) == 2 and extra[0]["instance_name"] == ""
                  and extra[0]["rows"] == [[None] * len(source["columns"])]
                  and exported["instances"][1:] == source["instances"],
                  "Station canonical empty default plus authored AUX", checks)
        elif all(not instance["rows"] for instance in source["instances"]):
            check(len(source["instances"]) == len(exported["instances"])
                  and all(old["instance_name"] == new["instance_name"]
                          and new["rows"] in ([], [[None] * len(source["columns"])])
                          for old, new in zip(source["instances"], exported["instances"])),
                  f"native empty placeholder {name}", checks)
        else:
            check(source["instances"] == exported["instances"], f"native rows {name}", checks)
    log = (RUN / "run.log").read_text(encoding="utf-8-sig")
    check("Station, 1 record inserted" in log and "Data successfully included" in log
          and "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0" in log
          and re.findall(r"\(warning #(\d+)\)", log) == ["108", "126"]
          and not re.search(r"\((?:error|notice) #", log),
          "MDB include and converter diagnostics", checks)
    check(sha(RUN / "model.log") == sha(PARENT_RUN / "model.log"), "native event log byte-identical to K02", checks)
    check(sha(RUN / "report-raw.json") == sha(PARENT_RUN / "report-raw.json"),
          "raw report byte-identical to K02", checks)
    result = {"schema": "simlox-k05-var05-mdb-author-validation/v1", "status": "PASS",
              "checks": len(checks), "run_id": contract["run_id"],
              "closure_sha256": sha(RUN / "closure.json"), "database_sha256": sha(RUN / "included.mdb"),
              "event_log_sha256": sha(RUN / "model.log"), "report_sha256": sha(RUN / "report-raw.json"),
              "check_names": checks}
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
