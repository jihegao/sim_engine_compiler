"""Deterministic append-stable source map. Root writes the canonical file once."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path
import sys
from make_source_inventory import HERE,body as inventory_body,candidate as inventory_candidate
from source_gate import REPO,RUN_ID,check,pin,parse,verify

SCHEMA="i03-var08-idle-maxut-prelaunch-manifest/v1"
CONTRACT_SHA="f23c6284afdaf25c7115f293907411ab941c0603b11d8bbf45d7fd8a5e671b41"
ROLE={
    "contract.json":"child_contract","execution-contract.json":"execution_binding",
    "native-input.json":"child_input","validate_native_cli.py":"behavior_validator",
    "run_native_ssh.ps1":"runner_script","review/independent_replay.py":"independent_replay",
    "review/independent_self_check.py":"independent_self_check",
}

def candidate(provisional=False,mode="sealed"):
    assert mode in ("live","sealed")
    verified=verify(mode)
    assert verified["counts"]=={"accepted_source_git_pairs":81,"mandatory_accepted_original_raw":108,
                                "required_docs":8,"installed":3}
    design=parse((HERE/"contract.json").read_bytes())
    lineage=design["lineage"]
    records=[];keys=set();paths=set()
    def add(key,path,wanted=None):
        absolute=path.resolve(strict=True)
        ident=str(absolute).lower()
        assert key not in keys and ident not in paths,(key,absolute)
        keys.add(key);paths.add(ident)
        got=pin(absolute.read_bytes())
        if wanted is not None:assert got=={name:wanted[name] for name in ("bytes","sha256")},(key,got,wanted)
        records.append({"key":key,"path":str(absolute),**got})
    owned=inventory_candidate(provisional)
    for row in owned["source_files"]:
        add(ROLE.get(row["relative_path"],"owned:"+row["relative_path"]),Path(row["path"]),row)
    if not provisional:
        path=HERE/"source-inventory.json"
        assert path.read_bytes()==inventory_body(owned)
        add("owned_source_inventory",path)
    for i,row in enumerate(lineage["accepted_81_local_and_base_git_refs"]):
        add(f"accepted_source:{i}",REPO/row["path"],row["disk"])
    for i,row in enumerate(lineage["mandatory_108_original_raw"]):
        add(f"accepted_raw:{i}",Path(row["path"]),row)
    for i,(relative,wanted) in enumerate(lineage["required_docs_8"].items()):
        path=REPO/relative
        if str(path.resolve(strict=True)).lower() not in paths:add(f"required_doc:{i}",path,wanted)
        else:check(path,wanted)
    for field,wanted in lineage["installed_exe_manual_dictionary_3"].items():
        add("installed:"+field,Path(wanted["path"]),wanted)
    helper=REPO/"cases/simlox-air-support/I03-var05-in-zero-delay-v1.0.0/captured_process.ps1"
    expected={"bytes":(HERE/"captured_process.ps1").stat().st_size,
              "sha256":"17285b90093c2d80c6241e1345b9926a2e4dd0f0b2b24f831c84c1cfa885b794"}
    assert check(HERE/"captured_process.ps1",expected)==expected
    add("accepted_capture_helper_ancestry",helper,expected)
    return {"schema":SCHEMA,"run_id":RUN_ID,"contract_sha256":CONTRACT_SHA,
            "execution_binding_sha256":pin((HERE/"execution-contract.json").read_bytes())["sha256"],
            "source_count":len(records),"source_files":records,
            "live_catalog_prelaunch_pin":{"path":str((REPO/"cases/simlox-air-support/publication-index-v1.json").resolve(strict=True)),
                                         **lineage["catalog_local_495"]},
            "historical_catalog_prefix_always_checked":495,
            "accepted_source_git_pairs":81,"accepted_raw_records":108,
            "accepted_nonclosure_raw":93,"accepted_closure_records":8,
            "accepted_invocation_records":7,"new_native_runs_authorized_by_manifest":0,
            "independent_method_state":"provisional" if provisional else "exact methods pinned; fresh approval required"}

def body(doc):return (json.dumps(doc,ensure_ascii=False,sort_keys=True,indent=2)+"\n").encode("utf-8")

def main():
    args=sys.argv[1:]
    assert args in ([],["--dry"],["--provisional"],["--write"])
    provisional=args==["--provisional"]
    mode="live" if args in (["--write"],["--provisional"]) else "sealed"
    data=body(candidate(provisional,mode))
    output=HERE/"prelaunch-manifest.json"
    if args==["--write"]:
        assert not output.exists(),"canonical manifest exists"
        output.write_bytes(data)
    elif args==[]:
        assert output.is_file() and output.read_bytes()==data
    print(json.dumps({"schema":"i03-var08-idle-maxut-manifest-check/v1",
                      "source_count":json.loads(data)["source_count"],
                      "manifest_sha256":hashlib.sha256(data).hexdigest(),
                      "written":args==["--write"],"provisional":provisional,"mode":mode},sort_keys=True))

if __name__=="__main__":main()
