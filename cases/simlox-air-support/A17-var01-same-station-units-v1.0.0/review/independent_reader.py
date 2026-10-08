"""Independent A17.var01 source, log, report, and protocol reader.

Only Python's standard library is imported. The same frozen predicates serve
the prospective fixture, actual preflight, and recovered original run bytes.
"""
from __future__ import annotations

import copy
import datetime
import hashlib
import json
import math
import re
import sys
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[4]
PARENT = REPO / "cases/simlox-air-support/A17-multi-unit-group-v1.0.0"
PARENT_RUN = PARENT / "runs/a17-v100-ssh-20260929-01"
CONTRACT_SHA = "d878f097ca7f021982628691a1c61c8b64633bc235de6fd9c8b116da587aed0b"
FORMS_SHA = "71eeec318ba6b7bd5b19a527891b5fd3125b7d66e7d59c9a30f41314ecad8c32"
REPORT_SHA = "3ae5e69163f8d211afc23de49346c2cd2ca87a7ca80fb825831ed0cedd291c7b"
PARENT_AUTHORED_SHA = "66d3eef1e1cf42d26971af9719feb68e7ec3ecd4ed188a8477f8cbe0918bb974"
PARENT_EXPORT_SHA = "819bbdd65799d20441191f41ca4a5d4df9aaf658466dd49dd952707d96943a42"
PARENT_LOG_SHA = "ae6c8430c26490c16e98f7ea66a0137ea7bcd1e309c1f2ba46a44940a0e7f33e"
PARENT_REPORT_SHA = "fcd289233082398dfa8531475719a6b068dadc841486d050ec71f6815356a8f4"
PDESC = "A17.var01 two explicit units at BASE-01 serving one group mission; no transfer"
HOMES = {0: "TEACH-UNIT", 1: "TEACH-UNIT-2"}
MISSION = "<BASIC-MISSION,TEACH-GROUP,0,0,0>"
RUN_ID = "a17-var01-same-station-v100-ssh-20261008-01"
RUN = str(CASE / "runs" / RUN_ID)
BASE = "3699aef69d56d3fc1573b50a23b25fec30b5b837"
PYTHON = r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
EXE = r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"
WORKING_DIRECTORY = r"C:\Users\user\Documents\Codex\2026-09-26\simlox-j35-event-parity\workspace"
SOURCE_PIN = "1a31cf6c10ed6b6bdaf2403a18e983c0ee286eba17a7b4dd513dc33ecdb2f795"
NEGATIVE_PATH = REPO / "cases/simlox-air-support/I04-var05-zero-transport-between-v1.0.0/runs/i04-var05-zero-transport-between-v100-ssh-20261008-01/model-run.log"
NEGATIVE_PIN = {"bytes":1122,"sha256":"ca209899bce7e299b49d9a482469efd8c0fee0d9f56673ffb99783cbf689457a"}
EXE_PIN = {"bytes":33196032,"sha256":"fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"}
PYTHON_PIN = {"bytes":106448,"sha256":"10d845f50a2af64e3500bb2fcb348b5bc98a75d8ddada63e45ba1da6a1fc79d1"}
TOOLS = ["build.py","source_gate.py","self_check.py","make_source_inventory.py","make_prelaunch_manifest.py"]
STAGES = ["import","export","check_import_export","calc","jsonreport","check_behavior"]
SPECIAL = {"run_native_ssh.ps1":"runner_script","validate_native_cli.py":"behavior_validator",
           "prospective-contract.json":"prospective_contract","execution-contract.json":"execution_binding",
           "native-input.json":"child_input"}
OWNED = (
    ".gitattributes","build.py","captured_process.ps1","check_roundtrip.py",
    "checker_receipt.ps1","child-roundtrip-oracle.json","event_ledger.py",
    "exact-diff.json","execution-contract.json","make_prelaunch_manifest.py",
    "make_source_inventory.py","model_common.py","native-input.json",
    "preflight_receipt.ps1","prospective-complete-log-forms.json","prospective-contract.json",
    "prospective-contract.md","prospective-log-graph.json","prospective-report-oracle.json",
    "report_oracle.py","run_native_ssh.ps1","self_check.py","source_gate.py",
    "ssh_transport.py","test_converter_gate.ps1","validate_native_cli.py",
    "preserved-context/independent-construction-go.md",
    "preserved-context/root-selection-receipt.json",
    "preserved-design/build_prospective.py","preserved-design/close_log_forms.py",
    "preserved-design/contract-v2.json","preserved-design/contract.json",
    "preserved-design/finalize_design.py","preserved-design/log-oracle.json",
    "preserved-development/self-check-v1-duplicate-swap.md",
    "preserved-development/self-check-v1-duplicate-swap.py.bytes",
    "preserved-development/model-common-v1-object-order.py.bytes",
    "preserved-development/inventory-v1-before-object-order.py.bytes",
    "preserved-development/model-common-v1-object-order.md",
    "preserved-development/template-i04-var10-checker_receipt.ps1.bytes",
    "preserved-development/template-i04-var10-preflight_receipt.ps1.bytes",
    "preserved-development/template-i04-var10-run_native_ssh.ps1.bytes",
    "preserved-development/template-i04-var10-ssh_transport.py.bytes",
    "preserved-development/template-i04-var10-test_converter_gate.ps1.bytes",
    "review/independent_reader.py","review/independent_self_check.py",
    "review/preserved-independent-selfcheck-v1-before-native-marker.py.bytes",
    "review/preserved-independent-selfcheck-v1-before-native-marker.md",
    "review/preserved-independent-reader-v1-before-object-order.py.bytes",
    "review/preserved-independent-reader-v1-before-object-order.md",
    "review/independent-static-go-2026-10-08.md",
    "source-maps/accepted-source-pairs.json","source-maps/prospective-source-pins.json",
)
MANIFEST_KEYS = set("schema run_id native_run_directory file_line_ascii_bytes file_line_ascii_max base_commit contract_sha256 execution_binding_sha256 input_sha256 source_inventory_sha256 runner_sha256 validator_sha256 independent_reader_sha256 source_count source_files owned_source_count accepted_source_pair_count required_local_source_count mandatory_original_count archived_catalog_count converter_negative_original_count installed_executable_count catalog_prefix_entries live_catalog_prelaunch_pin pure_tools stages native_commands pure_checkers new_native_runs_authorized_by_manifest independent_method_state".split())
PREFLIGHT_KEYS = set("schema run_id native_run_directory run_dirs_absent file_line_ascii_bytes file_line_ascii_max native_run_path_ancestors_no_reparse ssh_session ps_major ssh_ancestors mutex_free wts_active_gui_count gui accepted_source_pair_count required_local_source_count mandatory_original_count archived_catalog_count converter_negative_original_count installed_executable_count catalog_prefix_entries manifest_sha256 source_map_sha256 source_hashes source_hashes_after_pure pure_proof_directory pure_proof_path pure_proof_sha256 pure_checks native_process_started".split())
PROOF_KEYS = set("schema mode run_id native_run_directory manifest_sha256 source_map_sha256 started_utc completed_utc status error checks source_hashes_after".split())
PURE_STEP_KEYS = set("tool program arguments started_utc completed_utc status error child_pid child_session_id exit_code capture_error stdout_path stderr_path stdout_bytes stderr_bytes stdout_sha256 stderr_sha256".split())
APPROVAL_KEYS = set("schema decision run_id native_run_directory manifest_sha256 runner_sha256 validator_sha256 contract_sha256 execution_binding_sha256 input_sha256 source_map_sha256 independent_reader_sha256 preflight_relative_path preflight_sha256".split())
INVOCATION_KEYS = set("schema run_id created_utc original_run_dir native_run_directory input_sha256 contract_sha256 manifest_sha256 approval_sha256 approved_preflight_path approved_preflight_sha256 independent_reader_sha256 runner_script_sha256 session_id ssh_ancestors gui queue_mutex working_directory planned_commands planned_checkers source_hashes_before source_hashes_after_pure pure_proof_path pure_proof_sha256 pure_checks publication_state".split())
CLOSURE_KEYS = set("schema run_id native_run_directory invocation_sha256 manifest_sha256 approval_sha256 approved_preflight_sha256 source_hashes_before source_hashes_after raw step_error error publication_state".split())
STEP_KEYS = set("sequence name program arguments started_utc completed_utc child_pid child_session_id exit_code capture_error stdout_path stderr_path stdout_bytes stderr_bytes stdout_sha256 stderr_sha256 converter_log_bytes converter_log_sha256 converter_log_validated gui_preserved status error".split())


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def pinned(path: Path, sha: str) -> bytes:
    data = path.read_bytes()
    assert digest(data) == sha, path
    return data


def sealed(path: Path) -> dict:
    data = path.read_bytes()
    return {"bytes":len(data),"sha256":digest(data)}


def exact_pin(path: Path, pin: dict, *, readonly=False) -> None:
    assert set(pin) == {"bytes","sha256"}
    assert type(pin["bytes"]) is int and pin["bytes"] >= 0
    assert type(pin["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}",pin["sha256"])
    assert sealed(path) == pin, path
    if readonly:
        assert path.stat().st_file_attributes & 1, path


def exact_keys(value, keys) -> None:
    assert type(value) is dict and set(value) == set(keys), (set(value),set(keys))


def exact_int(value, expected) -> None:
    assert type(value) is int and value == expected


def exact_bool(value, expected) -> None:
    assert type(value) is bool and value is expected


def absolute(path: str) -> Path:
    assert type(path) is str
    candidate = Path(path)
    assert candidate.is_absolute() and candidate == candidate.resolve(strict=True)
    return candidate


def source_document():
    doc = unique_pairs((CASE/"source-inventory.json").read_bytes())
    exact_keys(doc,{"schema","source_count","source_files"})
    assert doc["schema"] == "a17-var01-source-inventory/v1"
    exact_int(doc["source_count"],len(OWNED))
    assert len(doc["source_files"]) == len(OWNED)
    for rel,row in zip(OWNED,doc["source_files"],strict=True):
        exact_keys(row,{"path","bytes","sha256"})
        assert row["path"] == rel
        assert not (CASE/rel).is_symlink()
        exact_pin(CASE/rel,{"bytes":row["bytes"],"sha256":row["sha256"]},readonly=True)
    return doc


def manifest_document():
    inv = source_document()
    doc = unique_pairs((CASE/"prelaunch-manifest.json").read_bytes())
    exact_keys(doc,MANIFEST_KEYS)
    assert doc["schema"] == "a17-var01-prelaunch-manifest/v1"
    assert doc["run_id"] == RUN_ID and type(doc["native_run_directory"]) is str
    assert doc["native_run_directory"] == RUN
    file_line = "File: " + str(Path(RUN)/"model.sxi").replace("\\","/")
    assert file_line.isascii()
    exact_int(doc["file_line_ascii_bytes"],len(file_line.encode("ascii")))
    exact_int(doc["file_line_ascii_bytes"],191)
    exact_int(doc["file_line_ascii_max"],199)
    assert doc["base_commit"] == BASE and doc["contract_sha256"] == CONTRACT_SHA
    pins = {"execution_binding_sha256":"execution-contract.json",
            "input_sha256":"native-input.json","source_inventory_sha256":"source-inventory.json",
            "runner_sha256":"run_native_ssh.ps1","validator_sha256":"validate_native_cli.py",
            "independent_reader_sha256":"review/independent_reader.py"}
    for key,rel in pins.items():
        assert doc[key] == sealed(CASE/rel)["sha256"]
    assert doc["input_sha256"] == SOURCE_PIN
    for key,expected in (("accepted_source_pair_count",41),("required_local_source_count",12),
                         ("mandatory_original_count",61),("archived_catalog_count",2),
                         ("converter_negative_original_count",1),("installed_executable_count",2),
                         ("catalog_prefix_entries",501),("native_commands",4),("pure_checkers",2),
                         ("new_native_runs_authorized_by_manifest",0)):
        exact_int(doc[key],expected)
    assert doc["pure_tools"] == TOOLS and doc["stages"] == STAGES
    assert doc["independent_method_state"] == "METHOD_ONLY_NO_NATIVE_APPROVAL"
    pairs = unique_pairs((CASE/"source-maps/accepted-source-pairs.json").read_bytes())
    source_pins = unique_pairs((CASE/"source-maps/prospective-source-pins.json").read_bytes())
    assert sealed(CASE/"source-maps/prospective-source-pins.json")["sha256"] == "65a64eba90bebc6efe31f186fd7108528529ab07caadd5e9f17afd567f878680"
    exact_pin(CASE/"source-maps/accepted-source-pairs.json",
              {"bytes":source_pins["accepted_source_pairs"]["bytes"],
               "sha256":source_pins["accepted_source_pairs"]["sha256"]})
    assert type(pairs) is list and len(pairs) == 41
    assert len(source_pins["required_local_sources"]) == 12
    assert len(source_pins["mandatory_originals"]) == 61
    expected = []
    for row in inv["source_files"]:
        rel = row["path"]
        expected.append({"key":SPECIAL.get(rel,"owned:"+rel),"path":str(CASE/rel),
                         "bytes":row["bytes"],"sha256":row["sha256"]})
    expected.append({"key":"owned:source-inventory.json","path":str(CASE/"source-inventory.json"),
                     **sealed(CASE/"source-inventory.json")})
    for row in pairs:
        exact_keys(row,{"path","oid","disk","git","byte_equal"})
        path = REPO/row["path"]
        assert exact_pin(path,row["disk"]) is None
        expected.append({"key":"accepted:"+row["path"],"path":str(path),**row["disk"]})
    for prefix,rows in (("required-local",source_pins["required_local_sources"]),
                        ("mandatory",source_pins["mandatory_originals"])):
        for index,row in enumerate(rows):
            path = absolute(row["path"])
            pin = {"bytes":row["bytes"],"sha256":row["sha256"]}
            exact_pin(path,pin)
            if prefix == "mandatory":
                assert path.stat().st_mode == row["original_mode"]
                assert path.stat().st_file_attributes == row["original_attributes"]
            expected.append({"key":f"{prefix}:{index:02d}","path":str(path),**pin})
    for label in ("catalog_local_501","catalog_git_501"):
        row = source_pins[label]
        path = absolute(row["path"])
        pin = {"bytes":row["bytes"],"sha256":row["sha256"]}
        exact_pin(path,pin)
        expected.append({"key":"archive:"+label,"path":str(path),**pin})
    exact_pin(NEGATIVE_PATH,NEGATIVE_PIN)
    expected.append({"key":"converter:failed-file-line-v100","path":str(NEGATIVE_PATH),**NEGATIVE_PIN})
    for key,path,pin in (("installed:simlox-exe",Path(EXE),EXE_PIN),
                         ("installed:python-runtime",Path(PYTHON),PYTHON_PIN)):
        exact_pin(path,pin)
        expected.append({"key":key,"path":str(path),**pin})
    exact_int(doc["owned_source_count"],len(OWNED)+1)
    exact_int(doc["source_count"],len(expected))
    assert len(doc["source_files"]) == len(expected)
    keys,by_path = set(),{}
    for actual,row in zip(doc["source_files"],expected,strict=True):
        exact_keys(actual,{"key","path","bytes","sha256"})
        assert actual == row
        folded = actual["key"].casefold()
        assert folded not in keys
        keys.add(folded)
        resolved = str(Path(actual["path"]).resolve(strict=True)).replace("/","\\").casefold()
        assert resolved not in by_path or by_path[resolved] == (actual["bytes"],actual["sha256"])
        by_path[resolved] = (actual["bytes"],actual["sha256"])
    exact_keys(doc["live_catalog_prelaunch_pin"],{"path","bytes","sha256"})
    catalog = REPO/"cases/simlox-air-support/publication-index-v1.json"
    assert doc["live_catalog_prelaunch_pin"]["path"] == str(catalog)
    return doc,{row["key"]:row["sha256"] for row in expected}


def map_digest(source_map: dict) -> str:
    assert type(source_map) is dict
    return digest(json.dumps(source_map,separators=(",",":"),ensure_ascii=False).encode("utf-8"))


def utc(value: str) -> datetime.datetime:
    assert type(value) is str
    parsed = datetime.datetime.fromisoformat(value.replace("Z","+00:00"))
    assert parsed.tzinfo is not None and parsed.utcoffset() == datetime.timedelta(0)
    return parsed


def preflight_receipt(path: Path):
    manifest,source_map = manifest_document()
    exact_pin(Path(manifest["live_catalog_prelaunch_pin"]["path"]),
              {"bytes":manifest["live_catalog_prelaunch_pin"]["bytes"],
               "sha256":manifest["live_catalog_prelaunch_pin"]["sha256"]})
    receipt = unique_pairs(path.read_bytes())
    exact_keys(receipt,PREFLIGHT_KEYS)
    assert receipt["schema"] == "a17-var01-ssh-preflight/v1"
    assert receipt["run_id"] == RUN_ID and type(receipt["native_run_directory"]) is str
    assert receipt["native_run_directory"] == RUN
    assert receipt["manifest_sha256"] == sealed(CASE/"prelaunch-manifest.json")["sha256"]
    assert receipt["source_map_sha256"] == map_digest(source_map)
    for field in ("source_hashes","source_hashes_after_pure"):
        assert receipt[field] == source_map
    for field,number in (("file_line_ascii_bytes",191),("file_line_ascii_max",199),
                         ("ssh_session",0),("ps_major",5),("wts_active_gui_count",1),
                         ("accepted_source_pair_count",41),("required_local_source_count",12),
                         ("mandatory_original_count",61),("archived_catalog_count",2),
                         ("converter_negative_original_count",1),("installed_executable_count",2),
                         ("catalog_prefix_entries",501)):
        exact_int(receipt[field],number)
    for field,value in (("run_dirs_absent",True),("native_run_path_ancestors_no_reparse",True),
                        ("mutex_free",True),("native_process_started",False)):
        exact_bool(receipt[field],value)
    assert type(receipt["ssh_ancestors"]) is list and "sshd.exe" in receipt["ssh_ancestors"]
    exact_keys(receipt["gui"],{"pid","session_id","start_unix_ms","responding"})
    for field,value in (("pid",13340),("session_id",1),("start_unix_ms",1790590196826)):
        exact_int(receipt["gui"][field],value)
    exact_bool(receipt["gui"]["responding"],True)
    pure_dir = absolute(receipt["pure_proof_directory"])
    assert pure_dir.parent == CASE/"test-output"
    assert re.fullmatch(r"preflight-pure-[0-9]{8}T[0-9]{13}Z-[0-9a-f]{8}",pure_dir.name)
    proof_path = pure_dir/"pure-proof.json"
    assert receipt["pure_proof_path"] == str(proof_path)
    assert receipt["pure_proof_sha256"] == sealed(proof_path)["sha256"]
    proof = unique_pairs(proof_path.read_bytes())
    exact_keys(proof,PROOF_KEYS)
    assert proof["schema"] == "a17-var01-pure-proof/v1"
    assert proof["mode"] == "preflight" and proof["status"] == "passed" and proof["error"] is None
    assert proof["run_id"] == RUN_ID and type(proof["native_run_directory"]) is str
    assert proof["native_run_directory"] == RUN
    assert proof["manifest_sha256"] == receipt["manifest_sha256"]
    assert proof["source_map_sha256"] == receipt["source_map_sha256"]
    assert proof["source_hashes_after"] == source_map
    assert type(proof["checks"]) is type(receipt["pure_checks"]) is list
    assert proof["checks"] == receipt["pure_checks"] and len(proof["checks"]) == len(TOOLS)
    previous = utc(proof["started_utc"])
    for tool,step in zip(TOOLS,proof["checks"],strict=True):
        exact_keys(step,PURE_STEP_KEYS)
        assert step["tool"] == tool and step["program"] == PYTHON
        assert step["arguments"] == f'-X utf8 -B "{CASE/tool}"'
        assert step["status"] == "completed" and step["error"] is None
        assert step["capture_error"] is None
        for field,expected in (("exit_code",0),("child_session_id",0),("stderr_bytes",0)):
            exact_int(step[field],expected)
        assert type(step["child_pid"]) is int and step["child_pid"] > 0
        started,completed = utc(step["started_utc"]),utc(step["completed_utc"])
        assert previous <= started <= completed
        previous = completed
        for stream in ("stdout","stderr"):
            expected_path = pure_dir/(Path(tool).stem+"-"+stream+".bin")
            assert step[stream+"_path"] == str(expected_path)
            exact_pin(expected_path,{"bytes":step[stream+"_bytes"],
                                     "sha256":step[stream+"_sha256"]})
    assert utc(proof["completed_utc"]) >= previous
    assert path.parent == CASE/"review"
    assert re.fullmatch(r"preflight-ssh0-[0-9]{8}T[0-9]{9}Z\.json",path.name)
    return receipt,source_map


def approval_document(path: Path):
    approval = unique_pairs(path.read_bytes())
    exact_keys(approval,APPROVAL_KEYS)
    assert approval["schema"] == "a17-var01-independent-prelaunch-go/v1"
    assert approval["decision"] == "GO_PRELAUNCH" and approval["run_id"] == RUN_ID
    assert type(approval["native_run_directory"]) is str and approval["native_run_directory"] == RUN
    manifest,source_map = manifest_document()
    for field,expected in (("manifest_sha256",sealed(CASE/"prelaunch-manifest.json")["sha256"]),
                           ("runner_sha256",manifest["runner_sha256"]),
                           ("validator_sha256",manifest["validator_sha256"]),
                           ("contract_sha256",CONTRACT_SHA),
                           ("execution_binding_sha256",manifest["execution_binding_sha256"]),
                           ("input_sha256",SOURCE_PIN),
                           ("source_map_sha256",map_digest(source_map)),
                           ("independent_reader_sha256",sealed(CASE/"review/independent_reader.py")["sha256"])):
        assert approval[field] == expected
    rel = approval["preflight_relative_path"].replace("\\","/")
    assert re.fullmatch(r"review/preflight-ssh0-[0-9]{8}T[0-9]{9}Z\.json",rel)
    preflight = CASE/rel
    assert preflight.is_file() and preflight.resolve(strict=True).parent == (CASE/"review").resolve(strict=True)
    assert approval["preflight_sha256"] == sealed(preflight)["sha256"]
    return approval,preflight_receipt(preflight)[0]


def unique_pairs(pairs):
    def hook(items):
        result = {}
        for key, value in items:
            assert key not in result, key
            result[key] = value
        return result
    return json.loads(pairs, object_pairs_hook=hook,
                      parse_constant=lambda value: (_ for _ in ()).throw(AssertionError(value)))


def type_value(actual, expected, dtype):
    if expected is None:
        assert actual is None
    elif dtype == "string":
        assert type(actual) is type(expected) is str and actual == expected
    elif dtype == "integer":
        assert type(actual) is type(expected) is int and actual == expected
    elif dtype == "double":
        assert type(actual) in (int, float) and type(expected) in (int, float)
        assert math.isfinite(actual) and math.isfinite(expected) and actual == expected
    else:
        raise AssertionError(dtype)


def typed_table(actual, expected):
    assert set(actual) == set(expected) == {"name", "columns", "instances"}
    assert type(actual["name"]) is type(expected["name"]) is str
    assert actual["name"] == expected["name"]
    assert actual["columns"] == expected["columns"]
    assert len(actual["instances"]) == len(expected["instances"])
    for a, b in zip(actual["instances"], expected["instances"], strict=True):
        assert set(a) == set(b) == {"instance_name", "rows"}
        assert type(a["instance_name"]) is type(b["instance_name"]) is str
        assert a["instance_name"] == b["instance_name"]
        assert len(a["rows"]) == len(b["rows"])
        for ra, rb in zip(a["rows"], b["rows"], strict=True):
            assert len(ra) == len(rb) == len(actual["columns"])
            for av, bv, col in zip(ra, rb, actual["columns"], strict=True):
                type_value(av, bv, col["datatype"])


def model_cells(model):
    return sum(len(row) for table in model["tables"] for inst in table["instances"] for row in inst["rows"])


def model_rows(model):
    return sum(len(inst["rows"]) for table in model["tables"] for inst in table["instances"])


def changed_model(parent, child):
    expected = copy.deepcopy(parent)
    unit = next(t for t in expected["tables"] if t["name"] == "Unit")
    assert [c["name"] for c in unit["columns"]][:3] == ["UNID", "DESCR", "STID"]
    assert len(unit["instances"]) == 1 and len(unit["instances"][0]["rows"]) == 2
    row = unit["instances"][0]["rows"][1]
    assert row[0] == "TEACH-UNIT-2" and row[2] == "BASE-02"
    row[2] = "BASE-01"
    problem = next(t for t in expected["tables"] if t["name"] == "ProblemDescription")
    assert problem["instances"][0]["rows"] == [["A17 two explicit units at two bases serving one group mission; no transfer"]]
    problem["instances"][0]["rows"] = [[PDESC]]
    assert set(child) == set(expected) == {"database_version", "tables"}
    assert type(child["database_version"]) is type(expected["database_version"])
    assert child["database_version"] == expected["database_version"]
    assert len(child["tables"]) == len(expected["tables"])
    for actual_table, expected_table in zip(child["tables"], expected["tables"], strict=True):
        typed_table(actual_table, expected_table)


def source_oracles():
    contract = unique_pairs(pinned(CASE/"prospective-contract.json", CONTRACT_SHA))
    assert contract["decision_stage"] == "PROSPECTIVE_DESIGN_ONLY"
    source_root = unique_pairs((CASE/"native-input.json").read_bytes())
    export_root = unique_pairs((CASE/"child-roundtrip-oracle.json").read_bytes())
    parent_source_root = unique_pairs(pinned(PARENT/"native-input.json", PARENT_AUTHORED_SHA))
    parent_export_root = unique_pairs(pinned(PARENT_RUN/"roundtrip-raw.json", PARENT_EXPORT_SHA))
    for root in (source_root, export_root, parent_source_root, parent_export_root):
        assert set(root) == {"model"}
        assert set(root["model"]) == {"database_version", "tables"}
    source, export = source_root["model"], export_root["model"]
    authored_parent, export_parent = parent_source_root["model"], parent_export_root["model"]
    changed_model(authored_parent, source)
    changed_model(export_parent, export)
    assert (len(source["tables"]), model_rows(source), model_cells(source)) == (33,20,203)
    assert (len(export["tables"]), model_rows(export), model_cells(export)) == (33,38,387)
    assert [t["name"] for t in source["tables"]] == [t["name"] for t in authored_parent["tables"]]
    return {"authored_tables":33,"authored_rows":20,"authored_cells":203,
            "export_tables":33,"export_rows":38,"export_cells":387}


def primary_lines():
    forms = unique_pairs(pinned(CASE/"prospective-complete-log-forms.json", FORMS_SHA))
    assert len(forms["full_forms"]) == 8
    primary = [x for x in forms["full_forms"] if x["status"] == "PRIMARY_CONTRACT_PASS_CANDIDATE"]
    assert len(primary) == 1 and primary[0]["arm_id"] == "unit0-controller0-return01"
    return primary[0]["lines"], primary[0]["crlf_sha256"]


READY_CHANGE = re.compile(r"Time: ([0-9.]+) <TEACH-AIR-01,([01])> nbr ready (increased|decreased) at unit: <(TEACH-UNIT(?:-2)?) at <(BASE-[0-9]+),([0-9]+)>>")
ALLOCATION = re.compile(r"Time: ([0-9.]+) " + re.escape(MISSION) + r" mission allocates system: <TEACH-AIR-01,([01])>")
PREP = re.compile(r"Time: ([0-9.]+) <TEACH-AIR-01,([01])> preparation (started|ended), mission: " + re.escape(MISSION))
TURN = re.compile(r"Time: ([0-9.]+) <TEACH-AIR-01,([01])> turnround (started|ended), mission: " + re.escape(MISSION) + r"(?: reduction factor: 1)?")
ARRIVE = re.compile(r"Time: ([0-9.]+) <TEACH-AIR-01,(BASE-[0-9]+),([0-9]+)> System arrives <TEACH-AIR-01,([01])>, mission success,  ?")
READY_CONTROLLER = re.compile(r"Time: ([0-9.]+) <TEACH-AIR-01,(BASE-[0-9]+),([0-9]+)> System ready <TEACH-AIR-01,([01])>")


def physical_ledger(lines):
    assert len(lines) == 60
    state = {i:{"home":HOMES[i],"ready":False,"assigned":False,"prep":False,
                "flight":False,"turn":False,"arrived":False,"ready_inc":0,"ready_dec":0,
                "prep_start":0,"prep_end":0,"turn_start":0,"turn_end":0,"controller_ready":0}
             for i in (0,1)}
    allocated = []
    arrivals = []
    mission_started = mission_task_started = mission_task_ended = mission_completed = False
    for pos, line in enumerate(lines, start=1):
        m = READY_CHANGE.fullmatch(line)
        if m:
            time, id_text, direction, unit, base, station_index = m.groups()
            i = int(id_text)
            s = state[i]
            assert unit == s["home"] and base == "BASE-01" and station_index == "0"
            if direction == "increased":
                assert time in ("0","10") and not s["ready"]
                if time == "10":
                    assert s["arrived"] and s["turn_end"] == 1
                s["ready"] = True
                s["ready_inc"] += 1
            else:
                assert time == "7" and s["ready"] and s["assigned"]
                s["ready"] = False
                s["ready_dec"] += 1
            continue
        m = ALLOCATION.fullmatch(line)
        if m:
            time, id_text = m.groups()
            i = int(id_text)
            s = state[i]
            assert time == "7" and s["ready"] and not s["assigned"]
            s["assigned"] = True
            allocated.append(i)
            continue
        m = PREP.fullmatch(line)
        if m:
            time, id_text, phase = m.groups()
            i = int(id_text)
            s = state[i]
            assert time == "7" and s["assigned"] and not s["ready"]
            if phase == "started":
                assert s["prep_start"] == 0 and s["prep_end"] == 0
                s["prep_start"] = 1
            else:
                assert s["prep_start"] == 1 and s["prep_end"] == 0
                s["prep_end"] = 1
                s["prep"] = True
            continue
        if line == "Time: 8 " + MISSION + " mission starting, duration: 2 : <TEACH-AIR-01,0>,<TEACH-AIR-01,1>":
            assert not mission_started and all(state[i]["prep"] for i in (0,1))
            mission_started = True
            for i in (0,1): state[i]["flight"] = True
            continue
        if line == "Time: 8.5 " + MISSION + " task starting: <TEACH-AIR-01,0>,<TEACH-AIR-01,1>":
            assert mission_started and not mission_task_started
            mission_task_started = True
            continue
        if line == "Time: 9.5 " + MISSION + " task completed: <TEACH-AIR-01,0>,<TEACH-AIR-01,1>":
            assert mission_task_started and not mission_task_ended
            mission_task_ended = True
            continue
        if line == "Time: 10 " + MISSION + " mission completed: <TEACH-AIR-01,0>,<TEACH-AIR-01,1>":
            assert mission_task_ended and not mission_completed
            mission_completed = True
            continue
        m = TURN.fullmatch(line)
        if m:
            time, id_text, phase = m.groups()
            i = int(id_text)
            s = state[i]
            assert time == "10" and mission_completed and s["flight"]
            if phase == "started":
                assert s["turn_start"] == 0 and s["turn_end"] == 0
                s["turn_start"] = 1
                s["turn"] = True
            else:
                assert s["turn_start"] == 1 and s["turn_end"] == 0
                s["turn_end"] = 1
            continue
        m = ARRIVE.fullmatch(line)
        if m:
            time, base, index, id_text = m.groups()
            i = int(id_text)
            s = state[i]
            assert time == "10" and base == "BASE-01" and index == "0"
            assert s["turn_end"] == 1 and not s["arrived"]
            s["arrived"] = True
            s["flight"] = False
            s["assigned"] = False
            arrivals.append(i)
            continue
        m = READY_CONTROLLER.fullmatch(line)
        if m:
            time, base, index, id_text = m.groups()
            i = int(id_text)
            s = state[i]
            assert time == "10" and base == "BASE-01" and index == "0"
            assert s["arrived"] and s["ready"]
            s["controller_ready"] += 1
    assert allocated == arrivals == [0,1]
    assert mission_started and mission_task_started and mission_task_ended and mission_completed
    for i in (0,1):
        s = state[i]
        assert s["ready"] and not s["assigned"] and not s["flight"]
        assert (s["ready_inc"],s["ready_dec"],s["prep_start"],s["prep_end"],
                s["turn_start"],s["turn_end"],s["controller_ready"]) == (2,1,1,1,1,1,2)
    return {"allocated":allocated,"arrived":arrivals,"terminal_ready":2,
            "unit_ready":{"TEACH-UNIT":1,"TEACH-UNIT-2":1}}


def log_bytes(data: bytes):
    assert data.count(b"\r\n") == 60 and data.endswith(b"\r\n")
    assert b"\n" not in data.replace(b"\r\n", b"")
    assert len(data) == 4039
    lines = data.decode("utf-8").split("\r\n")[:-1]
    ledger = physical_ledger(lines)
    expected, sha = primary_lines()
    assert lines == expected and digest(data) == sha
    assert sum(line.startswith("Time: ") for line in lines) == 52
    return {"full_lines":60,"timed_lines":52,"ledger":ledger}


def native_report_json(data: bytes):
    assert not data.startswith(b"\xef\xbb\xbf")
    assert b"\n" not in data.replace(b"\r\n", b"")
    marker = b",\r\n      ]"
    assert data.count(marker) == 1
    fixed = data.replace(marker, b"\r\n      ]")
    root = unique_pairs(fixed)
    assert set(root) == {"report"}
    assert set(root["report"]) == {"tables"}
    return root["report"]


def report_cells(report):
    return sum(len(row) for table in report["tables"] for inst in table["instances"] for row in inst["rows"])


def report_semantic(report, *, oracle_gate=True):
    c = unique_pairs(pinned(CASE/"prospective-contract.json", CONTRACT_SHA))
    expected = unique_pairs(pinned(CASE/"prospective-report-oracle.json", REPORT_SHA))
    assert set(report) == {"tables"}
    assert set(expected) == {"schema", "cell_count", "tables"}
    assert type(expected["cell_count"]) is int and expected["cell_count"] == 4044
    assert report_cells(report) == report_cells(expected) == c["report_cell_count"] == 4044
    assert [x["name"] for x in report["tables"]] == ["ProblemDescription","ResultSummary","SystemResults","StockTotalResults"]
    for a,b in zip(report["tables"], expected["tables"], strict=True):
        assert a["name"] == b["name"] and a["columns"] == b["columns"]
        assert len(a["instances"]) == len(b["instances"]) == 1
        assert a["instances"][0]["instance_name"] == b["instances"][0]["instance_name"]
        if oracle_gate:
            typed_table(a,b)
    tables = {t["name"]:t for t in report["tables"]}
    pdesc = tables["ProblemDescription"]["instances"][0]["rows"]
    assert len(pdesc) == 1 and len(pdesc[0]) == 1
    type_value(pdesc[0][0],PDESC,"string")
    summary = tables["ResultSummary"]
    summary_rows = summary["instances"][0]["rows"]
    expected_summary = [1,0,36,1,0,1,0,1,0,1,0]
    assert len(summary_rows) == 1 and len(summary_rows[0]) == len(expected_summary)
    for actual,expected_cell,column in zip(summary_rows[0],expected_summary,summary["columns"],strict=True):
        type_value(actual,expected_cell,column["datatype"])
    system = tables["SystemResults"]
    stock = tables["StockTotalResults"]
    assert len(system["instances"][0]["rows"]) == len(stock["instances"][0]["rows"]) == 72
    system_names = [x["name"] for x in system["columns"]]
    stock_names = [x["name"] for x in stock["columns"]]
    sys_constant = c["report_rules"]["SystemResults"]["constant_columns"]
    stock_constant = c["report_rules"]["StockTotalResults"]["constant_columns"]
    for i in range(72):
        t = i/2
        sr = {"UNID":"Total over all Units","SID":"Total over all Systems","STINT":t,"ETINT":t+0.5,
              "NSYRY":0 if 7<=t<10 else 2,"NSYMA":2 if 7<=t<10 else 0,
              "NSYMO":2 if 8<=t<10 else 0,"NSYMR":2 if 7<=t<8 else 0,
              "FTMO":1 if 8<=t<10 else 0,"STACC":2 if 8<=t<10 else 0}
        sr.update(sys_constant)
        st = {"STINT":t,"ETINT":t+0.5}
        st.update(stock_constant)
        for row, mapping, names, cols in ((system["instances"][0]["rows"][i],sr,system_names,system["columns"]),
                                          (stock["instances"][0]["rows"][i],st,stock_names,stock["columns"])):
            assert set(mapping) == set(names)
            for value,name,col in zip(row,names,cols,strict=True):
                type_value(value,mapping[name],col["datatype"])
    return {"tables":4,"rows":146,"cells":4044}


def converter_bytes(data: bytes) -> int:
    assert data and b"\n" not in data.replace(b"\r\n",b"")
    lines = data.decode("utf-8").split("\r\n")
    if lines[-1] == "":
        lines.pop()
    assert len(lines) == 17
    exact = [
        "Performing simulation",
        "Input file: " + str(Path(RUN)/"model.sxi"),
        "Output file: " + str(Path(RUN)/"model.sxo"),
        "Simulating.","Converting input data ...",
        "File: " + str(Path(RUN)/"model.sxi").replace("\\","/"),
        "Form: Control",
        "rec 1: (warning #108) Enabling simulation log may generate extensive data in log file",
        "Form: System",
        "rec 1: (warning #126) This system contains no items: TEACH-AIR-01",
        "Input conversion completed. Errors: 0, Warnings: 2, Notes: 0",
        None,"Starting simulation...",None,"Saving results ...",None,None,
    ]
    for actual,expected in zip(lines,exact,strict=True):
        if expected is not None:
            assert actual == expected
    for index,label in ((11,"Input data conversion time"),(13,"Simulation time"),
                        (15,"Result saving time"),(16,"Total execution time")):
        match = re.fullmatch(re.escape(label)+r": ([0-9]+(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?) secs\.",lines[index])
        assert match and math.isfinite(float(match.group(1))) and float(match.group(1)) >= 0
    file_line = lines[5].encode("ascii")
    assert len(file_line) == 191 and len(file_line) <= 199
    return len(lines)


def checker_receipt(data: bytes, name: str, raw: Path):
    body = unique_pairs(data)
    common = {"schema","passed","run_id","native_run_directory","input_sha256",
              "export_sha256","native_calls","issues"}
    if name == "check_import_export":
        keys = common|{"authored_tables","authored_rows","authored_cells",
                       "exported_tables","exported_rows","exported_cells"}
        schema = "a17-var01-roundtrip-check/v1"
    else:
        assert name == "check_behavior"
        keys = common|{"log_sha256","report_sha256","full_log_lines","timed_log_lines",
                       "log_arm","report_typed_cells","exported_cells","ready_by_unit"}
        schema = "a17-var01-native-behavior-check/v1"
    exact_keys(body,keys)
    assert body["schema"] == schema and body["run_id"] == RUN_ID
    exact_bool(body["passed"],True)
    assert type(body["native_run_directory"]) is str and body["native_run_directory"] == RUN
    assert body["input_sha256"] == SOURCE_PIN
    assert body["export_sha256"] == sealed(raw/"roundtrip-raw.json")["sha256"]
    exact_int(body["native_calls"],0)
    assert body["issues"] == []
    if name == "check_import_export":
        for field,value in (("authored_tables",33),("authored_rows",20),("authored_cells",203),
                            ("exported_tables",33),("exported_rows",38),("exported_cells",387)):
            exact_int(body[field],value)
    else:
        for field,file in (("log_sha256","model.log"),("report_sha256","report-raw.json")):
            assert body[field] == sealed(raw/file)["sha256"]
        for field,value in (("full_log_lines",60),("timed_log_lines",52),
                            ("report_typed_cells",4044),("exported_cells",387)):
            exact_int(body[field],value)
        assert body["log_arm"] == "unit0-controller0-return01"
        exact_keys(body["ready_by_unit"],{"TEACH-UNIT","TEACH-UNIT-2"})
        for value in body["ready_by_unit"].values():
            exact_int(value,1)
    return body


def sealed_replay(raw: Path):
    assert raw.is_dir() and raw != Path(RUN)
    manifest,source_map = manifest_document()
    approval,preflight = approval_document(CASE/"review/independent-prelaunch-go.json")
    assert raw.resolve(strict=True) != Path(RUN).resolve(strict=True)
    invocation = unique_pairs((raw/"invocation.json").read_bytes())
    closure = unique_pairs((raw/"closure.json").read_bytes())
    exact_keys(invocation,INVOCATION_KEYS)
    exact_keys(closure,CLOSURE_KEYS)
    assert invocation["schema"] == "a17-var01-invocation/v1"
    assert closure["schema"] == "a17-var01-closure/v1"
    for body in (invocation,closure):
        assert body["run_id"] == RUN_ID
        assert type(body["native_run_directory"]) is str and body["native_run_directory"] == RUN
        assert body["manifest_sha256"] == approval["manifest_sha256"]
        assert body["approval_sha256"] == sealed(CASE/"review/independent-prelaunch-go.json")["sha256"]
        assert body["approved_preflight_sha256"] == approval["preflight_sha256"]
        assert body["source_hashes_before"] == source_map
    assert invocation["original_run_dir"] == RUN
    assert invocation["input_sha256"] == SOURCE_PIN and invocation["contract_sha256"] == CONTRACT_SHA
    assert invocation["approved_preflight_path"] == str(CASE/approval["preflight_relative_path"])
    assert invocation["independent_reader_sha256"] == manifest["independent_reader_sha256"]
    assert invocation["runner_script_sha256"] == manifest["runner_sha256"]
    assert invocation["source_hashes_after_pure"] == source_map
    assert invocation["pure_checks"] and len(invocation["pure_checks"]) == len(TOOLS)
    assert invocation["queue_mutex"] == r"Global\SimloxIssue18NativeQueue"
    assert invocation["working_directory"] == WORKING_DIRECTORY
    assert invocation["publication_state"] == closure["publication_state"] == "not_published"
    exact_int(invocation["session_id"],0)
    assert type(invocation["ssh_ancestors"]) is list and "sshd.exe" in invocation["ssh_ancestors"]
    assert invocation["gui"] == preflight["gui"]
    def run_file(name):
        return str(Path(RUN)/name)
    commands = [
        {"name":"import","program":EXE,"arguments":f'-silent -jimport "{run_file("input.json")}" -save "{run_file("model.sxi")}" -log "{run_file("import.log")}" -close'},
        {"name":"export","program":EXE,"arguments":f'"{run_file("model.sxi")}" -silent -jexport "{run_file("roundtrip-raw.json")}" -log "{run_file("export.log")}" -close'},
        {"name":"calc","program":EXE,"arguments":f'"{run_file("model.sxi")}" -silent -threads 1 -calc -log "{run_file("model-run.log")}" -close'},
        {"name":"jsonreport","program":EXE,"arguments":f'"{run_file("model.sxo")}" -silent -jsonreport "{run_file("report-raw.json")}" -log "{run_file("report-export.log")}" -close'},
    ]
    checkers = [
        {"name":"check_import_export","program":PYTHON,"arguments":f'-X utf8 -B "{CASE/"check_roundtrip.py"}" --run-dir "{RUN}"'},
        {"name":"check_behavior","program":PYTHON,"arguments":f'-X utf8 -B "{CASE/"validate_native_cli.py"}" --run-dir "{RUN}"'},
    ]
    assert invocation["planned_commands"] == commands
    assert invocation["planned_checkers"] == checkers
    assert invocation["pure_proof_sha256"] == sealed(Path(invocation["pure_proof_path"]))["sha256"]
    native_proof = unique_pairs(Path(invocation["pure_proof_path"]).read_bytes())
    exact_keys(native_proof,PROOF_KEYS)
    assert native_proof["schema"] == "a17-var01-pure-proof/v1" and native_proof["mode"] == "native"
    assert native_proof["run_id"] == RUN_ID and native_proof["native_run_directory"] == RUN
    assert native_proof["status"] == "passed" and native_proof["error"] is None
    assert native_proof["checks"] == invocation["pure_checks"] and native_proof["source_hashes_after"] == source_map
    assert native_proof["manifest_sha256"] == approval["manifest_sha256"]
    assert native_proof["source_map_sha256"] == approval["source_map_sha256"]
    native_pure_dir = Path(invocation["pure_proof_path"]).parent
    assert native_pure_dir.parent == CASE/"test-output"
    assert re.fullmatch(r"native-pure-[0-9]{8}T[0-9]{13}Z-[0-9a-f]{8}",native_pure_dir.name)
    assert len(native_proof["checks"]) == len(TOOLS)
    previous = utc(native_proof["started_utc"])
    for tool,step in zip(TOOLS,native_proof["checks"],strict=True):
        exact_keys(step,PURE_STEP_KEYS)
        assert step["tool"] == tool and step["program"] == PYTHON
        assert step["arguments"] == f'-X utf8 -B "{CASE/tool}"'
        assert step["status"] == "completed" and step["error"] is None and step["capture_error"] is None
        for field,value in (("exit_code",0),("child_session_id",0),("stderr_bytes",0)):
            exact_int(step[field],value)
        assert type(step["child_pid"]) is int and step["child_pid"] > 0
        started,completed = utc(step["started_utc"]),utc(step["completed_utc"])
        assert previous <= started <= completed
        previous = completed
        for stream in ("stdout","stderr"):
            stream_path = native_pure_dir/(Path(tool).stem+"-"+stream+".bin")
            assert step[stream+"_path"] == str(stream_path)
            exact_pin(stream_path,{"bytes":step[stream+"_bytes"],"sha256":step[stream+"_sha256"]})
    assert utc(native_proof["completed_utc"]) >= previous
    invocation_utc = utc(invocation["created_utc"])
    assert invocation_utc >= utc(native_proof["completed_utc"])
    assert closure["invocation_sha256"] == sealed(raw/"invocation.json")["sha256"]
    assert closure["source_hashes_after"] == source_map
    assert closure["error"] in (None,"") and closure["step_error"] in (None,"")
    raw_map = closure["raw"]
    assert type(raw_map) is dict and len(raw_map) == 23
    actual_files = {x.name for x in raw.iterdir() if x.is_file()}
    assert actual_files == set(raw_map)|{"invocation.json","closure.json"}
    for name,pin in raw_map.items():
        assert "/" not in name and "\\" not in name and name not in ("invocation.json","closure.json")
        exact_pin(raw/name,pin,readonly=True)
    exact_pin(raw/"invocation.json",sealed(raw/"invocation.json"),readonly=True)
    exact_pin(raw/"closure.json",sealed(raw/"closure.json"),readonly=True)
    steps = unique_pairs((raw/"steps.json").read_bytes())
    assert type(steps) is list and len(steps) == 6
    assert [x["name"] for x in steps] == STAGES
    previous = invocation_utc
    for index,step in enumerate(steps):
        exact_keys(step,STEP_KEYS)
        exact_int(step["sequence"],index)
        exact_int(step["exit_code"],0)
        exact_int(step["child_session_id"],0)
        assert type(step["child_pid"]) is int and step["child_pid"] > 0
        assert step["capture_error"] is None and step["error"] is None
        assert step["status"] == "completed"
        exact_bool(step["gui_preserved"],True)
        exact_bool(step["converter_log_validated"],index==3)
        started,completed = utc(step["started_utc"]),utc(step["completed_utc"])
        assert previous <= started <= completed
        previous = completed
        expected_program = PYTHON if index in (2,5) else EXE
        assert step["program"] == expected_program
        planned = (invocation["planned_checkers"][0] if index==2 else
                   invocation["planned_checkers"][1] if index==5 else
                   invocation["planned_commands"][0 if index==0 else 1 if index==1 else 2 if index==3 else 3])
        exact_keys(planned,{"name","program","arguments"})
        assert planned["name"] == step["name"] and planned["program"] == step["program"]
        assert planned["arguments"] == step["arguments"]
        stdout = "roundtrip-validation.json" if index==2 else "author-validation.json" if index==5 else step["name"]+"-stdout.txt"
        stderr = step["name"]+"-stderr.txt"
        for stream,filename in (("stdout",stdout),("stderr",stderr)):
            assert step[stream+"_path"] == str(Path(RUN)/filename)
            exact_pin(raw/filename,{"bytes":step[stream+"_bytes"],"sha256":step[stream+"_sha256"]})
        exact_int(step["stderr_bytes"],0)
        if index==3:
            exact_pin(raw/"model-run.log",{"bytes":step["converter_log_bytes"],
                                           "sha256":step["converter_log_sha256"]},readonly=True)
        else:
            assert step["converter_log_bytes"] is None and step["converter_log_sha256"] is None
    assert sealed(raw/"input.json")["sha256"] == SOURCE_PIN
    assert converter_bytes((raw/"model-run.log").read_bytes()) == 17
    export_root = unique_pairs((raw/"roundtrip-raw.json").read_bytes())
    assert set(export_root) == {"model"}
    parent_export = unique_pairs(pinned(PARENT_RUN/"roundtrip-raw.json",PARENT_EXPORT_SHA))["model"]
    changed_model(parent_export,export_root["model"])
    assert log_bytes((raw/"model.log").read_bytes())["timed_lines"] == 52
    assert report_semantic(native_report_json((raw/"report-raw.json").read_bytes()))["cells"] == 4044
    checker_receipt((raw/"roundtrip-validation.json").read_bytes(),"check_import_export",raw)
    checker_receipt((raw/"author-validation.json").read_bytes(),"check_behavior",raw)
    return {"decision":"GO_BOUNDED","full_lines":60,"timed_lines":52,"report_cells":4044,
            "authored_cells":203,"export_cells":387,"raw_files":25}


def pure_fixture():
    source = source_oracles()
    log = primary_lines()[0]
    assert physical_ledger(log)["terminal_ready"] == 2
    raw = ("\r\n".join(log)+"\r\n").encode("utf-8")
    assert log_bytes(raw)["timed_lines"] == 52
    report = {"tables": unique_pairs(pinned(CASE/"prospective-report-oracle.json",REPORT_SHA))["tables"]}
    assert report_semantic(report)["cells"] == 4044
    return source


if __name__ == "__main__":
    if len(sys.argv) == 1 or sys.argv[1:] == ["--pure"]:
        result = pure_fixture()
    elif len(sys.argv) == 3 and sys.argv[1] == "--preflight-receipt":
        receipt,_ = preflight_receipt(Path(sys.argv[2]))
        result = {"decision":"PASS_ACTUAL_ZERO_NATIVE_PREFLIGHT",
                  "manifest_sha256":receipt["manifest_sha256"],
                  "source_map_sha256":receipt["source_map_sha256"],
                  "preflight_sha256":sealed(Path(sys.argv[2]))["sha256"]}
    elif len(sys.argv) == 3 and sys.argv[1] == "--evidence-dir":
        result = sealed_replay(Path(sys.argv[2]))
    else:
        raise SystemExit("usage: independent_reader.py [--pure | --preflight-receipt PATH | --evidence-dir DIR]")
    print(json.dumps(result,sort_keys=True))
