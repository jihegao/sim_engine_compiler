"""Exact source-role manifest. Root promotes an independently audited candidate."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from make_source_inventory import HERE, INVENTORY, document as inventory_document, encode
from model_common import INPUT_PIN, NATIVE_DIR, RUN_ID, seal
from source_gate import (REPO, SELECTED, SELECTED_PIN, ATTRIBUTES, ATTRIBUTES_PIN,
                         INSTALLED, ACCEPTED_PROOFS, CATALOG_CURRENT,
                         v100_failure_sources, v101_failure_sources, v102_failure_sources, exact, strict_json)

MANIFEST = HERE / "prelaunch-manifest.json"
CONTRACT_SHA = "012f9873ec0c62ab55314641213ffa9283b7eb8237df9b0d9d65564bea11d8f3"
SPECIAL = ("run_native_ssh.ps1", "validate_native_cli.py",
           "preserved-design/recovery-binding-v103.json", "execution-contract.json",
           "native-input.json")

def document() -> dict[str, object]:
    assert INVENTORY.read_bytes() == encode(inventory_document())
    inventory = strict_json(INVENTORY.read_bytes())
    selected = strict_json(exact(SELECTED, SELECTED_PIN))
    observed = strict_json(exact(ATTRIBUTES, ATTRIBUTES_PIN))
    assert inventory["schema"] == "i05-var04-source-inventory/v103"
    assert selected["merge"] == "7998e59944a8e061db2b48041349602039f4dc10"
    assert len(selected["source_pairs"]) == 21
    assert len(selected["accepted_parent_raw_seals"]) == len(observed["rows"]) == 12
    rows = [{"key":"owned:"+item["path"],
             "path":str(HERE / item["path"]),"bytes":item["bytes"],"sha256":item["sha256"]}
            for item in inventory["source_files"]]
    rows.append({"key":"owned:source-inventory.json","path":str(INVENTORY),**seal(INVENTORY)})
    for item in selected["source_pairs"]:
        path = (REPO / item["path"]).resolve(strict=True)
        assert path.is_relative_to(REPO.resolve(strict=True))
        assert seal(path) == {"bytes":item["bytes"],"sha256":item["sha256"]}
        rows.append({"key":"accepted:"+item["path"],"path":str(path),
                     "bytes":item["bytes"],"sha256":item["sha256"]})
    for i,(item,attr) in enumerate(zip(selected["accepted_parent_raw_seals"], observed["rows"], strict=True)):
        path=Path(item["path"])
        assert path.is_absolute() and attr["role"] == f"E05:raw:{i:02d}"
        assert all(attr[k] == item[k] for k in ("path","bytes","sha256"))
        assert seal(path) == {"bytes":item["bytes"],"sha256":item["sha256"]}
        assert path.stat().st_mode == attr["mode"] and path.stat().st_file_attributes == attr["file_attributes"]
        rows.append({"key":f"mandatory:{i:02d}","path":str(path),
                     "bytes":item["bytes"],"sha256":item["sha256"]})
    for name,(path,size,sha) in zip(("verdict","invocation","closure"),ACCEPTED_PROOFS,strict=True):
        assert seal(path)=={"bytes":size,"sha256":sha}
        assert path.stat().st_mode==33206 and path.stat().st_file_attributes==32
        rows.append({"key":"accepted-context:"+name,"path":str(path),"bytes":size,"sha256":sha})
    for name,(path,size,sha) in zip(("manual","dictionary","simlox-exe","python"),INSTALLED,strict=True):
        assert seal(path) == {"bytes":size,"sha256":sha}
        rows.append({"key":"installed:"+name,"path":str(path),"bytes":size,"sha256":sha})
    rows.extend(v100_failure_sources())
    rows.extend(v101_failure_sources())
    rows.extend(v102_failure_sources())
    assert len(rows) == inventory["source_count"] + 1 + 21 + 12 + 3 + 4 + 64 + 112 + 269
    assert len({row["key"].casefold() for row in rows}) == len(rows)
    identities:dict[str,tuple[int,str]]={}
    for row in rows:
        path=str(Path(row["path"]).resolve(strict=True)).replace("/","\\").casefold()
        pin=(row["bytes"],row["sha256"])
        assert identities.setdefault(path,pin)==pin, "aliased source roles disagree"
    for rel in SPECIAL:
        key="owned:"+rel
        found=[r for r in rows if r["key"]==key]
        assert len(found)==1 and found[0]["path"]==str(HERE / rel)
    binding=strict_json((HERE/"execution-contract.json").read_bytes())
    assert binding["schema"] == "i05-var04-execution-contract/v103"
    assert binding["native_run_directory"]==str(NATIVE_DIR)
    assert binding["recovery_binding_sha256"]==CONTRACT_SHA
    assert binding["export_serialization_sha256"]=="bab7315e63c301eccd7e004d9946d2b4db291279f3d65ec65a3c4cd4e3fca7b7"
    assert binding["authored_insertion_index"]==12 and binding["export_insertion_index"]==17
    assert binding["historical_v102_source_count"]==59 and binding["historical_v102_role_count"]==269
    assert binding["prospective_contract_sha256"]=="8bc2b9e7f579bfcfd75c025a9d7ac74ba385a09f70b744771d7937513d41eaf9"
    lines=["Input file: "+str(NATIVE_DIR/"model.sxi"),
           "Output file: "+str(NATIVE_DIR/"model.sxo"),
           "File: "+str(NATIVE_DIR/"model.sxi").replace("\\","/")]
    assert all(x.isascii() for x in lines) and [len(x.encode("ascii")) for x in lines]==[125,126,119]
    if MANIFEST.exists():
        catalog=strict_json(MANIFEST.read_bytes())["live_catalog_prelaunch_pin"]
        assert catalog["path"]==str(CATALOG_CURRENT)
    else:
        catalog={"path":str(CATALOG_CURRENT),**seal(CATALOG_CURRENT)}
    return {"schema":"i05-var04-prelaunch-manifest/v103","run_id":RUN_ID,
            "native_run_directory":str(NATIVE_DIR),"file_line_ascii_bytes":119,
            "file_line_ascii_max":199,"base_commit":selected["merge"],
            "contract_sha256":CONTRACT_SHA,
            "execution_binding_sha256":seal(HERE/"execution-contract.json")["sha256"],
            "input_sha256":INPUT_PIN["sha256"],
            "source_inventory_sha256":seal(INVENTORY)["sha256"],
            "runner_sha256":seal(HERE/"run_native_ssh.ps1")["sha256"],
            "validator_sha256":seal(HERE/"validate_native_cli.py")["sha256"],
            "independent_reader_sha256":seal(HERE/"review/independent_reader.py")["sha256"],
            "source_count":len(rows),"source_files":rows,
            "owned_source_count":inventory["source_count"]+1,
            "accepted_source_pair_count":21,"required_local_source_count":0,
            "mandatory_original_count":12,"archived_catalog_count":2,
            "accepted_context_count":3,
            "historical_v100_role_count":64,"historical_v100_source_count":54,
            "historical_v101_role_count":112,"historical_v101_source_count":57,
            "historical_v102_role_count":269,"historical_v102_source_count":59,
            "converter_negative_original_count":0,"installed_source_count":4,
            "catalog_prefix_entries":504,"live_catalog_prelaunch_pin":catalog,
            "pure_tools":["build.py","source_gate.py","self_check.py",
                          "make_source_inventory.py","make_prelaunch_manifest.py"],
            "stages":["import","export","check_import_export","calc","jsonreport","check_behavior"],
            "native_commands":4,"pure_checkers":2,
            "new_native_runs_authorized_by_manifest":0,
            "independent_method_state":"SOURCE_CONSTRUCTION_ONLY_NO_SSH_OR_NATIVE_APPROVAL"}

def main() -> None:
    parser=argparse.ArgumentParser()
    group=parser.add_mutually_exclusive_group()
    group.add_argument("--candidate",type=Path)
    group.add_argument("--write",action="store_true")
    args=parser.parse_args()
    body=encode(document())
    if args.candidate is not None:
        assert args.candidate.is_absolute() and not args.candidate.is_relative_to(HERE)
        with args.candidate.open("xb") as stream: stream.write(body)
    elif args.write:
        with MANIFEST.open("xb") as stream: stream.write(body)
    else:
        assert MANIFEST.read_bytes()==body
    print(json.dumps({"schema":"i05-var04-prelaunch-manifest-check/v103",
                      "passed":True,"source_count":document()["source_count"],
                      "sha256":hashlib.sha256(body).hexdigest()},sort_keys=True))

if __name__=="__main__":
    main()
