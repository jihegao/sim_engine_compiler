"""Read-only independent I03.var02 v1.0.2 contract/parent byte audit."""

import hashlib
import json
import re
import struct
import subprocess
from copy import deepcopy
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
REPO = next(p for p in HERE.parents if (p / ".git").exists())
BASE = "2e9f1e178056469a9903640ff970a5f2375274d4"
CONTRACT = {"bytes": 58038, "sha256": "1f058ae8706d4de81c28099b6580619eb4cb879e20314619f387839d9150ee29"}


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


def typed_equal(a, b):
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(typed_equal(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(typed_equal(x, y) for x, y in zip(a, b))
    return a == b


def append_valid(archive, live):
    if not isinstance(archive, dict) or not isinstance(live, dict) or archive.keys() != live.keys():
        return False
    if not isinstance(archive.get("entries"), list) or not isinstance(live.get("entries"), list):
        return False
    if len(archive["entries"]) != 490 or len(live["entries"]) < 490:
        return False
    if not all(typed_equal(archive[k], live[k]) for k in archive if k != "entries"):
        return False
    if not typed_equal(archive["entries"], live["entries"][:490]):
        return False
    keys = archive["entries"][-1].keys()
    ids = set()
    for entry in live["entries"]:
        if not isinstance(entry, dict) or entry.keys() != keys:
            return False
        if any(type(value) is not str for value in entry.values()):
            return False
        publication_id = entry["publication_id"]
        if not publication_id or publication_id in ids:
            return False
        ids.add(publication_id)
    return True


def main():
    contract = json.loads(exact(HERE / "contract.json", CONTRACT))
    assert (contract["case_id"], contract["variant_id"], contract["version"]) == ("I03", "I03.var02", "1.0.2")
    assert contract["ownership"]["base_commit"] == BASE
    assert contract["run_id"] == "i03-var02-idle-out-v102-ssh-20261007-01"
    assert not (HERE / "runs" / contract["run_id"]).exists()
    lineage = contract["source_lineage"]

    for key in ("root_selection_receipt", "root_live_context", "accepted_parent_index"):
        rec = lineage[key]
        exact(REPO / rec["path"], rec)
    catalog = lineage["catalog_at_selection"]
    historical = exact(HERE / catalog["owned_exact_archive"], catalog["owned_archive_pin"])
    assert catalog["owned_archive_pin"] == catalog["historical_original_at_selection_pin"] == catalog["local_disk"]
    assert pin(git_blob(BASE, catalog["path"])) == catalog["published_git_at_base"]
    live_raw = (REPO / catalog["path"]).read_bytes()
    live = json.loads(live_raw)
    old = json.loads(historical)
    assert len(old["entries"]) == catalog["entry_count_at_selection"] == 490
    assert typed_equal({k: v for k, v in old.items() if k != "entries"}, catalog["exact_metadata_at_selection"])
    assert append_valid(old, live)
    if len(live["entries"]) == 490:
        assert pin(live_raw) == catalog["historical_original_at_selection_pin"]
    assert catalog["historical_original_at_selection_is_not_future_live_byte_gate"] is True
    rules = catalog["postpublication_replay"]
    assert "prefix" in rules["live_rule"] and "whole-file SHA" in rules["live_whole_file_rule"]

    valid_append = deepcopy(old)
    added = dict(old["entries"][-1])
    added["publication_id"] = "I03.var02.audit-only.synthetic"
    valid_append["entries"].append(added)
    assert append_valid(old, valid_append)
    broken_prefix = deepcopy(valid_append)
    broken_prefix["entries"][0]["scope"] += " corrupted"
    assert not append_valid(old, broken_prefix)
    broken_metadata = deepcopy(valid_append)
    broken_metadata["as_of"] += " changed"
    assert not append_valid(old, broken_metadata)
    wrong_type = deepcopy(valid_append)
    wrong_type["as_of"] = True
    assert not append_valid(old, wrong_type)
    wrong_entry_type = deepcopy(valid_append)
    wrong_entry_type["entries"][-1]["case_id"] = True
    assert not append_valid(old, wrong_entry_type)
    duplicate = deepcopy(valid_append)
    duplicate["entries"][-1]["publication_id"] = old["entries"][-1]["publication_id"]
    assert not append_valid(old, duplicate)
    missing_key = deepcopy(valid_append)
    del missing_key["meaning"]
    assert not append_valid(old, missing_key)

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
    assert len(lineage["owned_historical_root_context"]) == 6
    assert len(lineage["excluded_v101_NO_GO_files"]) == 15
    histories = (lineage["excluded_v100_NO_GO_files"] + lineage["owned_historical_root_context"] +
                 lineage["excluded_v101_NO_GO_files"])
    assert len(histories) == 26
    for rec in histories:
        exact(HERE / rec["owned_inert_copy"], rec)
        assert Path(rec["owned_inert_copy"]).name != ".gitattributes"
        original = REPO / rec["original_path"]
        if original.exists():
            assert rec["original_if_present_must_match"] is True
            exact(original, rec)

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

    print(json.dumps({"schema": "i03-var02-independent-contract-audit/v102",
                      "decision": "GO_CONTRACT_ONLY",
                      "contract_sha256": CONTRACT["sha256"], "accepted_source_pairs": 20,
                      "accepted_run_records": 34, "installed": 3, "owned_history_copies": 27,
                      "parent_report_cells": 5210, "binary32_parent_means": 5,
                      "live_catalog_prefix_entries": 490, "valid_append_passes": True,
                      "invalid_append_probes_rejected": 6,
                      "new_run_absent": True}, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
