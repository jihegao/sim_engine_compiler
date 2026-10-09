"""Read-only custody for the selected B04 turnround arm and fixed I05.var07 oracle."""
from __future__ import annotations

import hashlib
import json
import stat
import subprocess
from pathlib import Path

from model_common import HERE, REPO, NATIVE_DIR, exact, no_reparse_ancestry, strict_json, typed_equal

SELECTION = HERE / "source-maps/root-selection-record.json"
SELECTION_PIN = {"bytes":35711,"sha256":"83896d1ba886926df481d4ae2f6addb0c9f1dba7fd6a7065e8df18e022d9a593"}
LOCAL_ARCHIVE = HERE / "source-maps/catalog-local-505.json.bytes"
GIT_ARCHIVE = HERE / "source-maps/catalog-git-505.json.bytes"
LOCAL_PIN = {"bytes":551394,"sha256":"3946c8b0e849a2c4fec850e0866b3095a97db235def11682a7108a35bc081539"}
GIT_PIN = {"bytes":546569,"sha256":"139dae3260e764a90c4f4d228a4fd34eda98c9b6baf17904ff0727ee08fc7fde"}
BASE = "120adb3d8912acfe9965ea04c939867721f3ede3"
LIVE_CATALOG = REPO / "cases/simlox-air-support/publication-index-v1.json"
PRIOR_MAP = REPO / "cases/simlox-air-support/I05-var04-scheduled-item-repair-v1.0.3/source-maps/root-selection-record.json"
PRIOR_PIN = {"bytes":9645,"sha256":"57d53ce82f61d7408c33ab9380e6b5cf4921e93846bb470d7b3fd61b19004b25"}
LIVE = REPO / "tmp/i05-var07-root-live-eligibility-v100-20261009-01.json"
LIVE_PIN = {"bytes":2184,"sha256":"d2339daa9773dc4c2ff7f5c4fb47a669751d0a517c53fccb3f812a0544fd4995"}
MANUAL_SOURCES = REPO / "cases/simlox-air-support/manual-sources-v2.json"
MANUAL_PIN = {"bytes":6199,"sha256":"9f145c99fefe9cb751b763331ca983dc889f0fd4e003af3ac466efd25f5e5608"}
PYTHON = Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
PYTHON_ROW = {"bytes":106448,"sha256":"10d845f50a2af64e3500bb2fcb348b5bc98a75d8ddada63e45ba1da6a1fc79d1",
              "mode":511,"attributes":32}
V100_FREEZE = REPO / "tmp/i05-var07-author-freeze-case-v100-20261009-01.json"
V100_FREEZE_ROW = {"bytes":6474,"sha256":"92a612a9821ae04c78c26f71684e66751c5ea6975e8b71917a4bce538c9ea182",
                   "mode":292,"attributes":33}
V100_STATIC_NO_GO = REPO / "tmp/i05-var07-root-static-nogo-v100-20261009-01.json"
V100_STATIC_NO_GO_ROW = {"bytes":2975,"sha256":"65528d82ad38be5c1f52c3b0635570b11863fb85b5de4e4a369f25d7031376c7",
                        "mode":292,"attributes":33}
PROSPECTIVE = {
    "native-input.json": (43997,"1dc116829e92845735440f6e7e49b0f1b768247b59af651538ae23db450a6619"),
    "preserved-design/expected-export.json": (48181,"4faa5ce52c1bf53b8ea6c1082304ae8429169ae19d496a680bcb4ef7a380a3d4"),
    "preserved-design/expected-model.log": (9108,"dc00ee98683714508de8ef483b19d9efc7484c24a08f57886250c902a2c8e445"),
    "preserved-design/expected-report.json": (93721,"30ca074dacfdb854f561453ca0d16a384a8b0dbae957b78da2edca4cc4cf9fc3"),
    "preserved-design/materialization-receipt.json": (4797,"91da0d5dadf5fdb1659687ee8b24ca0a4a7c4082e5bb5a46e2bee1c41c1bf5a2"),
    "preserved-design/source-delta-v100.json": (3184,"4d4e702270888c35d66247f57c46e77fb7feb7de16725d7d5a55576eb1de9f90"),
    "preserved-design/event-oracle-v100.json": (2724,"b10dc3205cae71766b8fb909e714bb71f7c73eb346b4712d335f1821f9adc4e6"),
    "preserved-design/report-oracle-v101.json": (2988,"69108a290de814b4a9b586978c8ba8001771ef2ab72de2214a2b1e3dcf76b808"),
    "preserved-design/prospective-contract-v100.json": (6378,"c34bb3d2b9c88763347f63e5bb111389db00e800d743ff74102e810eab6df0b7"),
    "preserved-design/README-prospective-v100.md": (2775,"0bfdd99a12ce4940d07cf92f030a7d8b97f2875d19ea9a92219a1c2ea6cf4694"),
    "review/independent-source-eligibility-go-v100.json": (2520,"eeec49da9cde34c15a11d07c07544e71f1047544a3aa519b8ef62878afd3095c"),
    "review/independent-pure-method-go-v100.json": (4018,"5b41e6de54ec273aee94d7e21df43a2c34db5f07dab1b7924a252e373b9cf9a9"),
    "review/independent-construction-go-v100.json": (4422,"6431f162e8df38418b464ecd793cdfb092f3e646250f22f2288c4918bd044200"),
}

def pin(path: Path, row: dict) -> None:
    exact(path, {"bytes":row["bytes"],"sha256":row["sha256"]})
    if "attributes" in row:
        assert path.stat().st_file_attributes == row["attributes"], ("attributes",str(path))
    if "mode" in row:
        assert stat.S_IMODE(path.stat().st_mode) == row["mode"], ("mode",str(path))

def selected() -> dict:
    data = strict_json(exact(SELECTION, SELECTION_PIN))
    assert type(data) is dict and data["schema"] == "i05-var07-root-selection-byte-audit/v100"
    assert data["decision"] == "ELIGIBLE_FOR_PROSPECTIVE_CONTRACT_REVIEW_ONLY"
    assert data["catalog_entries"] == 505 and data["candidate_published"] is False
    assert data["protected_original_count"] == 98 and data["role_reference_count"] == 100
    assert data["selected_parent_arm"]["role"] == "B04 turnround, not B04 no-turnround control"
    return data

def selected_roles(data: dict) -> list[dict]:
    refs: list[tuple[str,Path,dict]] = [("selected:live",LIVE,{**LIVE_PIN,"attributes":33,"mode":292}),
       ("selected:catalog",LIVE_CATALOG,data["catalog_local"]),
       ("selected:prior-map",PRIOR_MAP,{**PRIOR_PIN,"attributes":33,"mode":292}),
       ("selected:manual-sources",MANUAL_SOURCES,{**MANUAL_PIN,"attributes":32,"mode":438})]
    for group, rows in (("dependency",data["prior_dependency_pairs"]),("parent-source",data["accepted_parent_source_pairs"])):
        refs += [(f"selected:{group}:{i:02d}",REPO / row["path"],row) for i,row in enumerate(rows)]
    for group, rows in (("parent-raw",data["accepted_parent_raw_originals"]),("excluded-v100-raw",data["excluded_v100_raw_observed"])):
        refs += [(f"selected:{group}:{i:02d}",Path(row["path"]),row) for i,row in enumerate(rows)]
    for group, runs in (("parent-receipt",data["accepted_parent_runs"]),("excluded-v100-receipt",data["excluded_v100_receipts_observed"])):
        for i,run in enumerate(runs):
            refs += [(f"selected:{group}:{i:02d}:{name}",Path(run[name+"_path"]),run[name]) for name in ("invocation","closure")]
    assert set(data["installed_sources"])=={"dictionary","executable","manual"}
    refs += [(f"selected:installed:{name}",Path(data["installed_sources"][name]["path"]),
              data["installed_sources"][name]) for name in ("dictionary","executable","manual")]
    assert len(refs) == 100
    seen: dict[str,tuple] = {}
    output = []
    for key,path,row in refs:
        assert path.is_absolute()
        no_reparse_ancestry(path)
        resolved=path.resolve(strict=True)
        assert str(resolved).casefold()==str(path).casefold(), ("alias path",key)
        path=resolved
        pin(path,row)
        identity = str(path).casefold()
        value = (row["bytes"],row["sha256"],row["mode"],row["attributes"])
        assert seen.setdefault(identity,value) == value, ("alias",key)
        output.append({"key":key,"path":str(path),"bytes":row["bytes"],"sha256":row["sha256"],
                       "mode":row["mode"],"attributes":row["attributes"]})
    assert len(seen) == 98
    direct=data["selected_parent_arm"]
    assert any(row["path"].casefold()==direct["path"].casefold() and row["sha256"]==direct["sha256"] for row in output)
    return output

def git_pairs(rows: list[dict]) -> None:
    assert len(rows)==37
    by_path={}
    for row in rows:
        path=row["path"]
        assert type(path) is str and path and "\\" not in path
        if path in by_path:
            first=by_path[path]
            assert all(row[key]==first[key] for key in ("oid","bytes","sha256","mode","attributes")), ("pair alias",path)
        else:
            by_path[path]=row
    assert len(by_path)==35 and len({row["oid"] for row in by_path.values()})==35
    proc=subprocess.run(["git","ls-tree","-r","--full-tree",BASE,"--",*by_path],
                        cwd=REPO,stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True)
    found={}
    for line in proc.stdout.decode("ascii").splitlines():
        fields,path=line.split("\t",1)
        mode,kind,oid=fields.split()
        assert mode=="100644" and kind=="blob" and path not in found
        found[path]=oid
    assert set(found)==set(by_path)
    for path,row in by_path.items():
        assert found[path]==row["oid"]
        blob=subprocess.run(["git","cat-file","blob",row["oid"]],cwd=REPO,
                            stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True).stdout
        assert len(blob)==row["bytes"] and hashlib.sha256(blob).hexdigest()==row["sha256"]

def verify(require_absent_native: bool=False) -> dict:
    data=selected()
    roles=selected_roles(data)
    pin(PYTHON,PYTHON_ROW)
    pin(V100_FREEZE,V100_FREEZE_ROW)
    prior_freeze=strict_json(V100_FREEZE.read_bytes())
    assert prior_freeze["schema"]=="i05-var07-author-freeze-case/v100"
    assert prior_freeze["source_list_count"]==40 and prior_freeze["present_author_count"]==37
    pin(V100_STATIC_NO_GO,V100_STATIC_NO_GO_ROW)
    prior_no_go=strict_json(V100_STATIC_NO_GO.read_bytes())
    assert prior_no_go["schema"]=="i05-var07-root-static-source-nogo/v100"
    assert prior_no_go["decision"]=="STATIC_NO_GO" and prior_no_go["native_dispatch"] is False
    assert prior_no_go["package_method_invocations"]==0 and prior_no_go["ssh_preflight_invocations"]==0
    assert prior_no_go["actual_failed_invocation"] is None
    git_pairs(data["prior_dependency_pairs"]+data["accepted_parent_source_pairs"])
    assert len(data["accepted_parent_raw_originals"])==len(data["excluded_v100_raw_observed"])==24
    assert len(data["accepted_parent_runs"])==len(data["excluded_v100_receipts_observed"])==2
    for rel,(size,sha) in PROSPECTIVE.items():
        pin(HERE / rel,{"bytes":size,"sha256":sha,"attributes":33})
    pin(LOCAL_ARCHIVE,{**LOCAL_PIN,"attributes":33})
    pin(GIT_ARCHIVE,{**GIT_PIN,"attributes":33})
    baseline=strict_json(exact(LOCAL_ARCHIVE,LOCAL_PIN))
    git=strict_json(exact(GIT_ARCHIVE,GIT_PIN))
    assert typed_equal(baseline,git)
    current=strict_json(LIVE_CATALOG.read_bytes())
    assert type(current) is type(baseline) is dict and set(current)==set(baseline)
    assert set(baseline)=={"schema","as_of","catalog_snapshot","entry_publication_state","meaning","entries"}
    assert baseline["schema"]=="simlox-air-support-publication-index/v1"
    assert type(current["entries"]) is type(baseline["entries"]) is list
    assert len(current["entries"])==len(baseline["entries"])==505
    for catalog in (baseline,current):
        ids=[]
        for entry in catalog["entries"]:
            assert type(entry) is dict
            for key in ("publication_id","case_id","version","package","evidence","scope"):
                assert type(entry.get(key)) is str and entry[key]
            ids.append(entry["publication_id"])
        assert len(set(ids))==len(ids)
    assert typed_equal(current["entries"][:505],baseline["entries"])
    if require_absent_native: assert not NATIVE_DIR.exists()
    return {"schema":"i05-var07-source-gate/v101","passed":True,
            "selected_reference_count":len(roles),"selected_unique_original_count":98,
            "accepted_source_pair_count":37,"accepted_source_pair_unique_count":35,
            "accepted_raw_count":24,"excluded_raw_count":24,
            "runtime_source_count":1,"historical_source_count":2,
            "catalog_prefix_entries":505,"native_dispatch":False}

if __name__=="__main__":
    print(json.dumps(verify(),sort_keys=True,separators=(",",":")))
