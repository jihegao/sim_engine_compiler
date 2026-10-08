"""Read-only source, accepted raw and append-aware catalog verifier."""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
from build import construct,parse,typed_equal
from copy_context import candidate as context_candidate
from copy_pure_proof import candidate as pure_proof_candidate

HERE=Path(__file__).resolve().parent
REPO=HERE.parents[2]
GIT=Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\native\git\cmd\git.exe")
CONTRACT_SHA="f23c6284afdaf25c7115f293907411ab941c0603b11d8bbf45d7fd8a5e671b41"
INPUT_SHA="38a2b5c0e7f75ec477557e87c200424cdabc859e11c9e5db3ca15ecaace4bb05"
CONTEXT_SHA="daf611857b7a9caf85061287ff5ed02ebc6ce4a5ad37acab93248fa8946f74d2"
RUN_ID="i03-var08-idle-maxut-out-v100-ssh-20261008-01"
CATALOG_REL="cases/simlox-air-support/publication-index-v1.json"

def pin(data):return {"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest()}
def check(path,want):
    assert path.is_file(),("missing mandatory original",str(path))
    got=pin(path.read_bytes())
    assert got=={k:want[k] for k in ("bytes","sha256")},(str(path),got,want)
    return got

def git_tree(base):
    p=subprocess.run([str(GIT),"ls-tree","-r","-z",base],cwd=REPO,capture_output=True)
    assert p.returncode==0,p.stderr.decode(errors="replace")
    rows={}
    for item in p.stdout.split(b"\0"):
        if item:
            meta,name=item.split(b"\t",1)
            _,kind,oid=meta.split(b" ")
            assert kind==b"blob"
            key=name.decode("utf-8")
            assert key not in rows
            rows[key]=oid.decode("ascii")
    return rows

def git_blob(tree,path):
    assert path in tree,path
    p=subprocess.run([str(GIT),"cat-file","blob",tree[path]],cwd=REPO,capture_output=True)
    assert p.returncode==0,p.stderr.decode(errors="replace")
    return p.stdout

def catalog(design,tree,mode):
    lineage=design["lineage"]
    archive=(HERE/"preserved-context/context-17.bytes").read_bytes()
    base_copy=(HERE/"preserved-context/context-18.bytes").read_bytes()
    assert pin(archive)==lineage["catalog_local_495"]
    assert pin(base_copy)=={k:lineage["catalog_git_495"][k] for k in ("bytes","sha256")}
    assert tree[CATALOG_REL]==lineage["catalog_git_495"]["oid"]
    assert git_blob(tree,CATALOG_REL)==base_copy
    live_bytes=(REPO/CATALOG_REL).read_bytes()
    if mode=="live":assert pin(live_bytes)==lineage["catalog_local_495"],"prelaunch catalog whole-byte drift"
    historical=parse(archive);live=parse(live_bytes)
    assert set(historical)==set(live) and "entries" in historical
    assert type(historical["entries"]) is type(live["entries"]) is list
    assert len(historical["entries"])==495 and len(live["entries"])>=495
    assert typed_equal({k:v for k,v in historical.items() if k!="entries"},
                       {k:v for k,v in live.items() if k!="entries"})
    assert typed_equal(historical["entries"],live["entries"][:495])
    ids=[entry["publication_id"] for entry in live["entries"]]
    assert all(type(x) is str and x for x in ids) and len(ids)==len(set(ids))
    return {"historical_prefix_checked":495,"live_entries_observed":len(ids),
            "historical_archive_sha256":pin(archive)["sha256"],
            "base_git_blob_sha256":pin(base_copy)["sha256"]}

def context(design):
    check(HERE/"context-custody.json",{"bytes":5844,"sha256":CONTEXT_SHA})
    mapping=parse((HERE/"context-custody.json").read_bytes())
    assert mapping["schema"]=="i03-var08-context-custody/v1" and len(mapping["records"])==19
    assert context_candidate()["map"]=={"bytes":5844,"sha256":CONTEXT_SHA}
    declared=design["lineage"]["selection_v2"]
    row=mapping["records"][0]
    assert row["original_path"]==str(Path(declared["path"]).relative_to(REPO)).replace("\\","/")
    assert {k:row[k] for k in ("bytes","sha256")}=={k:declared[k] for k in ("bytes","sha256")}
    for row in mapping["records"]:
        check(HERE/row["owned_copy"],row)
    return {"owned_copies_checked":19,"map_sha256":CONTEXT_SHA}

def verify(mode="live"):
    assert mode in ("live","sealed")
    check(HERE/"contract.json",{"bytes":105915,"sha256":CONTRACT_SHA})
    design=parse((HERE/"contract.json").read_bytes())
    assert design["schema"]=="simlox-i03-var08-prospective-contract-design/v2"
    assert design["proposed_run_absent"]==RUN_ID
    tree=git_tree(design["lineage"]["base_commit"])
    refs=design["lineage"]["accepted_81_local_and_base_git_refs"]
    assert len(refs)==len({r["path"] for r in refs})==81
    for row in refs:
        check(REPO/row["path"],row["disk"])
        assert tree[row["path"]]==row["oid"]
        assert pin(git_blob(tree,row["path"]))==row["git"]
    raw=design["lineage"]["mandatory_108_original_raw"]
    assert len(raw)==len({r["path"] for r in raw})==108
    closures=sum(Path(r["path"]).name=="closure.json" for r in raw)
    invocations=sum(Path(r["path"]).name=="invocation.json" for r in raw)
    assert (len(raw)-closures-invocations,closures,invocations)==(93,8,7)
    for row in raw:check(Path(row["path"]),row)
    docs=design["lineage"]["required_docs_8"]
    assert len(docs)==8
    for relative,want in docs.items():check(REPO/relative,want)
    installed=design["lineage"]["installed_exe_manual_dictionary_3"]
    assert len(installed)==3
    for want in installed.values():check(Path(want["path"]),want)
    c=context(design)
    proof=pure_proof_candidate()
    assert proof["copies"]==13 and proof["map"]=={
        "bytes":6127,"sha256":"25092b41ebef6a4123407c5ac4754b27b8e1e1d1549b02d87ccecd2029b33618"}
    cat=catalog(design,tree,mode)
    parent_path=Path(design["lineage"]["parent"]["source"]["path"])
    parent=parse(parent_path.read_bytes())
    assert check(HERE/"native-input.json",{"bytes":47391,"sha256":INPUT_SHA})
    assert typed_equal(parse((HERE/"native-input.json").read_bytes()),construct(parent,design))
    run=HERE/"runs"/RUN_ID
    if mode=="live":assert not run.exists(),("run already exists",str(run))
    return {"schema":"i03-var08-source-gate/v1","mode":mode,
            "counts":{"accepted_source_git_pairs":81,"mandatory_accepted_original_raw":108,
                      "required_docs":8,"installed":3},"context":c,"catalog":cat,
            "pure_proof_copies_checked":13,"run_absent_observed":not run.exists(),"input_sha256":INPUT_SHA,
            "contract_sha256":CONTRACT_SHA}

if __name__=="__main__":
    ap=argparse.ArgumentParser();ap.add_argument("--mode",choices=("live","sealed"),default="live")
    print(json.dumps(verify(ap.parse_args().mode),sort_keys=True))
