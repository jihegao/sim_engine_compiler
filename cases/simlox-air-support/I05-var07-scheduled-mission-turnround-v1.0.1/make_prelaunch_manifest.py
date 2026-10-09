"""Exact ordered source-role manifest; root alone promotes a reviewed candidate."""
from __future__ import annotations

import argparse
import hashlib
import json
import stat
from pathlib import Path

from make_source_inventory import HERE, INVENTORY, document as inventory_document, encode
from model_common import INPUT_PIN, NATIVE_DIR, RUN_ID, seal, strict_json
from source_gate import (REPO, BASE, LIVE_CATALOG, PYTHON, PYTHON_ROW, V100_FREEZE,
                         V100_FREEZE_ROW, V100_STATIC_NO_GO, V100_STATIC_NO_GO_ROW,
                         selected, selected_roles, verify as verify_source)

MANIFEST=HERE/"prelaunch-manifest.json"
CONTRACT_SHA="c34bb3d2b9c88763347f63e5bb111389db00e800d743ff74102e810eab6df0b7"
SPECIAL=("run_native_ssh.ps1","validate_native_cli.py","preserved-design/prospective-contract-v100.json",
         "execution-contract.json","native-input.json")

def document() -> dict[str,object]:
    assert INVENTORY.read_bytes()==encode(inventory_document())
    inventory=strict_json(INVENTORY.read_bytes())
    assert inventory["schema"]=="i05-var07-source-inventory/v101"
    source_verdict=verify_source()
    assert source_verdict["selected_reference_count"]==100
    assert source_verdict["accepted_source_pair_count"]==37
    assert source_verdict["accepted_source_pair_unique_count"]==35
    assert source_verdict["historical_source_count"]==2
    selection=selected()
    rows=[]
    for item in inventory["source_files"]:
        path=HERE/item["path"]
        assert path.stat().st_file_attributes==33
        rows.append({"key":"owned:"+item["path"],"path":str(path),**seal(path),
                     "mode":stat.S_IMODE(path.stat().st_mode),"attributes":33})
    rows.append({"key":"owned:source-inventory.json","path":str(INVENTORY),**seal(INVENTORY),
                 "mode":stat.S_IMODE(INVENTORY.stat().st_mode),"attributes":INVENTORY.stat().st_file_attributes})
    rows.extend(selected_roles(selection))
    rows.append({"key":"runtime:python","path":str(PYTHON),**PYTHON_ROW})
    rows.append({"key":"historical:v100-author-freeze","path":str(V100_FREEZE),**V100_FREEZE_ROW})
    rows.append({"key":"historical:v100-static-no-go","path":str(V100_STATIC_NO_GO),**V100_STATIC_NO_GO_ROW})
    assert len(rows)==inventory["source_count"]+104
    assert len({r["key"].casefold() for r in rows})==len(rows)
    aliases={}
    for row in rows:
        identity=str(Path(row["path"]).resolve(strict=True)).replace("/","\\").casefold()
        pin=(row["bytes"],row["sha256"],row["mode"],row["attributes"])
        assert aliases.setdefault(identity,pin)==pin
    for rel in SPECIAL:
        role=[r for r in rows if r["key"]=="owned:"+rel]
        assert len(role)==1 and role[0]["path"]==str(HERE/rel)
    binding=strict_json((HERE/"execution-contract.json").read_bytes())
    assert binding["schema"]=="i05-var07-execution-contract/v101"
    assert binding["logical_run_id"]==RUN_ID and binding["native_run_directory"]==str(NATIVE_DIR)
    assert binding["prospective_contract_sha256"]==CONTRACT_SHA
    assert binding["authored_insertion_index"]==binding["export_insertion_index"]==32
    assert binding["selected_reference_count"]==100 and binding["selected_unique_original_count"]==98
    assert binding["accepted_source_disk_git_pairs"]==37 and binding["accepted_source_disk_git_unique_paths"]==35
    assert binding["historical_source_count"]==2
    lines=["Input file: "+str(NATIVE_DIR/"model.sxi"),
           "Output file: "+str(NATIVE_DIR/"model.sxo"),
           "File: "+str(NATIVE_DIR/"model.sxi").replace("\\","/")]
    assert all(line.isascii() for line in lines)
    assert [len(line.encode("ascii")) for line in lines]==[125,126,119]
    if MANIFEST.exists():
        catalog=strict_json(MANIFEST.read_bytes())["live_catalog_prelaunch_pin"]
        assert catalog["path"]==str(LIVE_CATALOG)
    else:
        catalog={"path":str(LIVE_CATALOG),**seal(LIVE_CATALOG)}
    return {"schema":"i05-var07-prelaunch-manifest/v101","run_id":RUN_ID,
            "native_run_directory":str(NATIVE_DIR),"file_line_ascii_bytes":119,
            "file_line_ascii_max":199,"base_commit":BASE,"contract_sha256":CONTRACT_SHA,
            "execution_binding_sha256":seal(HERE/"execution-contract.json")["sha256"],
            "input_sha256":INPUT_PIN["sha256"],"source_inventory_sha256":seal(INVENTORY)["sha256"],
            "runner_sha256":seal(HERE/"run_native_ssh.ps1")["sha256"],
            "validator_sha256":seal(HERE/"validate_native_cli.py")["sha256"],
            "independent_reader_sha256":seal(HERE/"review/independent_reader.py")["sha256"],
            "source_count":len(rows),"source_files":rows,"owned_source_count":inventory["source_count"]+1,
            "selected_reference_count":100,"selected_unique_original_count":98,
            "accepted_source_pair_count":37,"accepted_source_pair_unique_count":35,
            "accepted_raw_count":24,"excluded_raw_count":24,
            "archived_catalog_count":2,"installed_source_count":3,"runtime_source_count":1,
            "historical_source_count":2,
            "catalog_prefix_entries":505,"live_catalog_prelaunch_pin":catalog,
            "pure_tools":["build.py","source_gate.py","self_check.py","make_source_inventory.py","make_prelaunch_manifest.py"],
            "stages":["import","export","check_import_export","calc","jsonreport","check_behavior"],
            "native_commands":4,"pure_checkers":2,"new_native_runs_authorized_by_manifest":0,
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
    print(json.dumps({"schema":"i05-var07-prelaunch-manifest-check/v101","passed":True,
                      "source_count":document()["source_count"],"sha256":hashlib.sha256(body).hexdigest()},sort_keys=True))

if __name__=="__main__": main()
