"""Read-only byte audit of frozen I03.var02 v1.0.0 contract and parents."""

import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
REPO = next(p for p in HERE.parents if (p / ".git").exists())
BASE = "2e9f1e178056469a9903640ff970a5f2375274d4"
CONTRACT_SHA = "7020f5b51496f10ff2d7ba53ca8f8acdc3fb727c596c5f776068573c3cff5539"


def pin(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def exact(path, record):
    raw = path.read_bytes()
    assert pin(raw) == {"bytes": record["bytes"], "sha256": record["sha256"]}, str(path)
    return raw


def git_blob(revision, path):
    return subprocess.check_output(["git", "show", f"{revision}:{path}"], cwd=REPO)


def main():
    raw = exact(HERE / "contract.json", {"bytes": 41930, "sha256": CONTRACT_SHA})
    contract = json.loads(raw)
    assert contract["case_id"] == "I03" and contract["variant_id"] == "I03.var02"
    assert contract["version"] == "1.0.0" and contract["ownership"]["base_commit"] == BASE
    assert contract["run_id"] == "i03-var02-idle-out-v100-ssh-20261007-01"
    assert not (HERE / "runs" / contract["run_id"]).exists()
    lineage = contract["source_lineage"]
    exact(REPO / lineage["root_selection_receipt"]["path"], lineage["root_selection_receipt"])
    exact(REPO / lineage["root_live_context"]["path"], lineage["root_live_context"])
    exact(REPO / lineage["accepted_parent_index"]["path"], lineage["accepted_parent_index"])
    catalog = lineage["catalog_at_selection"]
    exact(REPO / catalog["path"], catalog["local_disk"])
    assert pin(git_blob(BASE, catalog["path"])) == catalog["published_git_at_base"]
    assert catalog["local_disk"] != catalog["published_git_at_base"]

    source_records = lineage["accepted_source_local_vs_published_git_at_base"]
    assert len(source_records) == 20
    for record in source_records:
        exact(REPO / record["path"], record["local_disk"])
        assert pin(git_blob(BASE, record["path"])) == record["published_git_at_base"], record["path"]

    raw_records = lineage["accepted_original_run_records"]
    assert len(raw_records) == 34
    for record in raw_records:
        exact(Path(record["path"]), record)
    assert sum(record["sha256"] == lineage["parent_run_closure_sha256"] for record in raw_records) == 1
    assert sum(record["sha256"] == lineage["parent_run_invocation_sha256"] for record in raw_records) == 1
    for record in lineage["accepted_dependencies"].values():
        assert hashlib.sha256((REPO / record["path"]).read_bytes()).hexdigest() == record["sha256"]
    for record in lineage["installed"].values():
        exact(Path(record["path"]), record)

    parent = json.loads((REPO / contract["scope"]["source_parent"]).read_bytes())
    transfer = next(t for t in parent["model"]["tables"] if t["name"] == "ResourceTransfer")
    assert [c["name"] for c in transfer["columns"]] == ["STFID", "STTID", "RID", "TFTIME", "TFQTY", "TFDT", "NOTE"]
    assert transfer["instances"][0]["rows"] == [["BASE-01", "<OUTSIDE>", "P-CREW", 7.75, 1, 0.0, None]]

    print(json.dumps({
        "schema": "i03-var02-independent-contract-audit/v100",
        "decision": "PINS_PASS_SEMANTIC_NO_GO",
        "contract_sha256": CONTRACT_SHA,
        "accepted_source_disk_git_pairs": len(source_records),
        "accepted_original_run_records": len(raw_records),
        "installed": len(lineage["installed"]),
        "context_records": 4,
        "new_run_absent": True,
    }, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
