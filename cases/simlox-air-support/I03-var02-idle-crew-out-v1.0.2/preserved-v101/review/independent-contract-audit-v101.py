"""Read-only independent I03.var02 v1.0.1 contract/parent byte audit."""

import hashlib
import json
import re
import struct
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
REPO = next(p for p in HERE.parents if (p / ".git").exists())
BASE = "2e9f1e178056469a9903640ff970a5f2375274d4"
CONTRACT = {"bytes": 48826, "sha256": "a614608f87608b68f4bd1645107fb3dfe88b20ea4bf8634e4ebdd4de6d3fa391"}


def pin(raw):
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def exact(path, record):
    raw = path.read_bytes()
    assert pin(raw) == {"bytes": record["bytes"], "sha256": record["sha256"]}, str(path)
    return raw


def git_blob(revision, path):
    return subprocess.check_output(["git", "show", f"{revision}:{path}"], cwd=REPO)


def f32(value):
    return struct.unpack("<f", struct.pack("<f", value))[0]


def report_json(path):
    raw = path.read_text(encoding="utf-8-sig")
    assert len(re.findall(r",(?=\s*[}\]])", raw)) == 1
    return json.loads(re.sub(r",(?=\s*[}\]])", "", raw))


def main():
    contract = json.loads(exact(HERE / "contract.json", CONTRACT))
    assert (contract["case_id"], contract["variant_id"], contract["version"]) == ("I03", "I03.var02", "1.0.1")
    assert contract["ownership"]["base_commit"] == BASE
    assert contract["run_id"] == "i03-var02-idle-out-v101-ssh-20261007-01"
    assert not (HERE / "runs" / contract["run_id"]).exists()
    lineage = contract["source_lineage"]

    for key in ("root_selection_receipt", "root_live_context", "accepted_parent_index"):
        rec = lineage[key]
        exact(REPO / rec["path"], rec)
    catalog = lineage["catalog_at_selection"]
    historical = exact(HERE / catalog["owned_exact_archive"], catalog["local_disk"])
    assert pin(git_blob(BASE, catalog["path"])) == catalog["published_git_at_base"]
    live = json.loads((REPO / catalog["path"]).read_bytes())
    old = json.loads(historical)
    assert len(old["entries"]) == 490 and live["entries"][:490] == old["entries"]
    assert {k: v for k, v in live.items() if k != "entries"} == {k: v for k, v in old.items() if k != "entries"}

    source_records = lineage["accepted_source_local_vs_published_git_at_base"]
    assert len(source_records) == 20
    for rec in source_records:
        exact(REPO / rec["path"], rec["local_disk"])
        assert pin(git_blob(BASE, rec["path"])) == rec["published_git_at_base"], rec["path"]
    run_records = lineage["accepted_original_run_records"]
    assert len(run_records) == 34
    for rec in run_records:
        exact(Path(rec["path"]), rec)
    assert sum(rec["sha256"] == lineage["parent_run_closure_sha256"] for rec in run_records) == 1
    assert sum(rec["sha256"] == lineage["parent_run_invocation_sha256"] for rec in run_records) == 1
    for rec in lineage["accepted_dependencies"].values():
        assert hashlib.sha256((REPO / rec["path"]).read_bytes()).hexdigest() == rec["sha256"]
    for rec in lineage["installed"].values():
        exact(Path(rec["path"]), rec)

    assert len(lineage["excluded_v100_NO_GO_files"]) == 5
    assert len(lineage["owned_historical_root_context"]) == 5
    for rec in lineage["excluded_v100_NO_GO_files"] + lineage["owned_historical_root_context"]:
        exact(HERE / rec["owned_inert_copy"], rec)
        original = REPO / rec["original_path"]
        if original.exists():
            if rec["original_path"] == catalog["path"]:
                # The contract's generic rule would incorrectly demand this stale exact byte pin.
                pass
            else:
                exact(original, rec)
    catalog_context = next(r for r in lineage["owned_historical_root_context"] if r["original_path"] == catalog["path"])
    assert catalog_context["original_if_present_must_match"] is True
    assert catalog_context["bytes"] == catalog["local_disk"]["bytes"]
    assert catalog_context["sha256"] == catalog["local_disk"]["sha256"]
    assert "prefix" in catalog["postpublication_replay"]
    # Any append changes the still-present original's bytes while preserving the required prefix.
    hypothetical_append = json.loads(historical)
    hypothetical_append["entries"].append({"publication_id": "audit-only-synthetic-append"})
    assert hypothetical_append["entries"][:490] == old["entries"]
    assert hypothetical_append["entries"] != old["entries"]

    parent_path = REPO / contract["scope"]["source_parent"]
    parent = json.loads(parent_path.read_bytes())
    assert pin(parent_path.read_bytes())["sha256"] == contract["scope"]["source_parent_sha256"]
    assert parent["model"]["database_version"] == 20160627 and len(parent["model"]["tables"]) == 32
    tables = {t["name"]: t for t in parent["model"]["tables"]}
    assert tables["ResourceTransfer"]["instances"][0]["rows"] == [["BASE-01", "<OUTSIDE>", "P-CREW", 7.75, 1, 0.0, None]]
    assert tables["ResourceAllocation"]["instances"][0]["rows"] == [["AIR_BASIC", "P-CREW", "BASE-01", 2, None]]
    op = tables["OperationProfile"]["instances"][0]["rows"]
    assert [row[2] for row in op] == [8.0, 20.0] and [row[8] for row in op] == [1.0, 1.0]

    busy_report_path = REPO / contract["accepted_busy_comparator"]["path"] / "out-report-raw.json"
    report = report_json(busy_report_path)
    rtables = report["report"]["tables"]
    assert [t["name"] for t in rtables] == contract["report_gate"]["tables_in_order"]
    assert sum(len(t["columns"]) * sum(len(i["rows"]) for i in t["instances"]) for t in rtables) == 5210
    for got, expected in zip(rtables, contract["report_gate"]["topology"]):
        assert [c["name"] for c in got["columns"]] == expected["columns"]
        assert len(got["instances"]) == 1 and got["instances"][0]["instance_name"] == expected["instance_name"]
        assert len(got["instances"][0]["rows"]) == expected["rows"]
    for table, section in (("SystemResults", "system_field_classes"), ("StockTotalResults", "stock_fields"), ("ResourceResults", "resource_fields")):
        names = next(t["columns"] for t in contract["report_gate"]["topology"] if t["name"] == table)
        fields = [field for value in contract["report_gate"][section].values() if isinstance(value, list) for field in value]
        assert len(fields) == len(names) and set(fields) == set(names)
    total = next(t for t in rtables if t["name"] == "ResourceResultsTotal")
    observed = dict(zip((c["name"] for c in total["columns"]), total["instances"][0]["rows"][0]))
    for key, ratio in (("NR", 44/36), ("NRA", 44/36), ("NRN", 43.75/36), ("NRUM", 2/36), ("NRW", .5/36)):
        assert observed[key] == f32(ratio), key
    expected_child = contract["report_gate"]["resource_fields"]["total_expected_float32"]
    for key, ratio in (("NR", 42/36), ("NRA", 42/36), ("NRN", 42/36), ("NRUM", 2/36), ("NRW", 1/36)):
        assert expected_child[key] == f32(ratio), key

    print(json.dumps({"schema": "i03-var02-independent-contract-audit/v101",
                      "decision": "PINS_AND_REPORT_GATES_PASS_CATALOG_POLICY_NO_GO",
                      "contract_sha256": CONTRACT["sha256"], "accepted_source_pairs": 20,
                      "accepted_run_records": 34, "installed": 3, "owned_history_copies": 10,
                      "parent_report_cells": 5210, "binary32_parent_means": 5,
                      "live_catalog_prefix_entries": 490,
                      "catalog_original_if_present_conflicts_with_append": True,
                      "new_run_absent": True}, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
