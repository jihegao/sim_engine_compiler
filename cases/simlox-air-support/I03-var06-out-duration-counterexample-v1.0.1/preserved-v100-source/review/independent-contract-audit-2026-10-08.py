"""Read-only exact-byte and contract-shape audit for I03.var06 v1.0.0."""

from __future__ import annotations

import hashlib
import json
import math
import struct
import subprocess
import copy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
PKG = Path(__file__).resolve().parents[1]
CONTRACT = PKG / "contract.json"
PARENT = ROOT / "cases/simlox-air-support/I03-var02-idle-crew-out-v1.0.2"
BASE = "3887a7fd5e387f078a716e49df62f894ce767700"
CONTRACT_SHA = "f03452c24030789f64a25df0419ffd574f97411a9ea0e1faa83df5743a22f793"
NOTE_SHA = "503942e65aa86d5d5465bc715b948c337e08edd275c8cc22dfeb6b64eb618190"
INDEX_SHA = "4060de5d7434ff675949b9eea7fb8f827ac0c72a56e530169b60ecb0da0724dc"


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def pin(path: Path, rec: dict) -> None:
    data = path.read_bytes()
    assert len(data) == rec["bytes"], (path, "size")
    assert sha(data) == rec["sha256"], (path, "sha")


def typed(a: object, b: object) -> bool:
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(typed(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(typed(x, y) for x, y in zip(a, b))
    return a == b


def blob_map(rev: str) -> dict[str, str]:
    raw = subprocess.check_output(["git", "ls-tree", "-r", "-z", rev], cwd=ROOT)
    out: dict[str, str] = {}
    for line in raw.split(b"\0"):
        if not line:
            continue
        meta, path = line.split(b"\t", 1)
        mode, kind, oid = meta.split()
        if kind != b"blob":
            continue
        name = path.decode("utf-8")
        assert name not in out
        out[name] = oid.decode("ascii")
    return out


def git_pin(path: str, rec: dict, blobs: dict[str, str]) -> None:
    data = subprocess.check_output(["git", "cat-file", "blob", blobs[path]], cwd=ROOT)
    assert len(data) == rec["bytes"] and sha(data) == rec["sha256"], path


def source_tables(path: Path) -> list[dict]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert doc["model"]["database_version"] == 20160627
    return doc["model"]["tables"]


def one_table(tables: list[dict], name: str) -> dict:
    found = [t for t in tables if t["name"] == name]
    assert len(found) == 1, name
    assert len(found[0]["instances"]) == 1
    return found[0]


def binary32(x: float) -> float:
    return struct.unpack("<f", struct.pack("<f", x))[0]


def valid_catalog_append(frozen: dict, candidate: dict) -> bool:
    if not typed({k: v for k, v in frozen.items() if k != "entries"},
                 {k: v for k, v in candidate.items() if k != "entries"}):
        return False
    old, new = frozen["entries"], candidate.get("entries")
    if not isinstance(new, list) or len(new) < len(old):
        return False
    if not all(typed(a, b) for a, b in zip(old, new)):
        return False
    ids = [x.get("publication_id") for x in new if isinstance(x, dict)]
    return len(ids) == len(new) and len(set(ids)) == len(ids)


def main() -> None:
    assert CONTRACT.stat().st_size == 174913 and sha(CONTRACT.read_bytes()) == CONTRACT_SHA
    note = PKG / "development-note.md"
    assert note.stat().st_size == 2485 and sha(note.read_bytes()) == NOTE_SHA
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    s = contract["source_lineage"]
    assert contract["case_id"] == "I03" and contract["variant_id"] == "I03.var06"
    assert contract["run_id"] == "i03-var06-out-dt4-v100-ssh-20261008-01"
    assert not (PKG / "native-input.json").exists()
    assert not (PKG / "runs" / contract["run_id"]).exists()
    assert s["base_commit"] == BASE
    assert subprocess.check_output(["git", "rev-parse", BASE], cwd=ROOT).decode().strip() == BASE
    blobs = blob_map(BASE)
    counts: dict[str, int] = {}

    for key, expected in (
        ("parent_source_disk_and_git_at_base", 192),
        ("accepted_dependency_source_disk_and_git_at_base", 20),
        ("accepted_secondary_context_source_disk_and_git_at_base", 2),
        ("accepted_dependency_summary", 2),
    ):
        records = s[key]
        assert len(records) == expected
        assert len({r["path"] for r in records}) == expected
        for rec in records:
            local = rec.get("local_disk", rec.get("local"))
            published = rec.get("published_git_at_base", rec.get("git"))
            pin(ROOT / rec["path"], local)
            git_pin(rec["path"], published, blobs)
            assert rec["byte_equal"] == (local == published)
        counts[key] = len(records)

    for key, expected in (
        ("accepted_parent_and_context_raw", 59),
        ("accepted_secondary_context_run_files", 59),
        ("installed", 3),
        ("required_docs", 8),
    ):
        records = s[key]
        assert len(records) == expected
        paths = []
        for rec in records:
            p = Path(rec.get("original_path", rec["path"])) if "path" in rec else Path(rec["original_path"])
            if not p.is_absolute():
                p = ROOT / p
            pin(p, rec)
            paths.append(str(p))
        assert len(paths) == len(set(paths))
        counts[key] = len(records)

    for key in ("authoritative_parent_index", "historical_parent_v1_index_NO_GO", "root_selection", "root_live_context", "parent_readonly_replay"):
        rec = s[key]
        p = Path(rec["path"])
        pin(p if p.is_absolute() else ROOT / p, rec)
    assert s["authoritative_parent_index"]["sha256"] == INDEX_SHA
    parent_index = json.loads((PARENT / "evidence-index-v2.json").read_text(encoding="utf-8"))
    assert len(parent_index["source_files"]) == 192
    assert len(parent_index["raw_files"]) == 59
    assert typed(s["accepted_parent_and_context_raw"], parent_index["raw_files"])
    assert {r["path"] for r in s["parent_source_disk_and_git_at_base"]} == {
        "cases/simlox-air-support/I03-var02-idle-crew-out-v1.0.2/" + r["path"]
        for r in parent_index["source_files"]
    }

    catalog = s["catalog_at_selection"]
    cat_path = ROOT / catalog["path"]
    pin(cat_path, catalog["local_disk"])
    git_pin(catalog["path"], catalog["published_git_at_base"], blobs)
    assert catalog["local_disk"] != catalog["published_git_at_base"]
    cat = json.loads(cat_path.read_text(encoding="utf-8"))
    assert len(cat["entries"]) == catalog["entry_count"] == 491
    assert typed({k: v for k, v in cat.items() if k != "entries"}, catalog["metadata"])
    assert s["parent_readonly_replay"]["original_checks"] == 14996
    assert s["parent_readonly_replay"]["postappend_checks"] == 14995
    assert s["parent_readonly_replay"]["other_verdict_fields_type_exact_equal"] is True
    assert "first491 entries unchanged" in catalog["replay_rule"]
    assert "only unique appended entries" in catalog["replay_rule"]
    test_append = copy.deepcopy(cat)
    new_entry = copy.deepcopy(cat["entries"][-1])
    new_entry["publication_id"] = "I03.var06.contract-audit-synthetic"
    test_append["entries"].append(new_entry)
    assert valid_catalog_append(cat, test_append)
    bad = copy.deepcopy(test_append)
    bad["entries"][0]["publication_id"] = "corrupted-prior-entry"
    assert not valid_catalog_append(cat, bad)
    bad = copy.deepcopy(test_append)
    bad["schema"] = 1
    assert not valid_catalog_append(cat, bad)
    bad = copy.deepcopy(test_append)
    bad["entries"][-1]["publication_id"] = bad["entries"][-2]["publication_id"]
    assert not valid_catalog_append(cat, bad)

    delta = contract["source_delta"]
    assert len(delta["allowed_changes_exactly"]) == 2
    assert {x["column"] for x in delta["allowed_changes_exactly"]} == {"PDESC", "TFDT"}
    assert delta["child_transfer_row"] == ["BASE-01", "<OUTSIDE>", "P-CREW", 6.0, 1, 4.0, None]
    pin(ROOT / delta["parent_input"]["path"], delta["parent_input"])
    tables = source_tables(ROOT / delta["parent_input"]["path"])
    assert len(tables) == 32 and len({t["name"] for t in tables}) == 32
    transfer = one_table(tables, "ResourceTransfer")
    assert transfer["instances"][0]["rows"] == [["BASE-01", "<OUTSIDE>", "P-CREW", 6.0, 1, 0.0, None]]
    assert one_table(tables, "ResourceAllocation")["instances"][0]["rows"] == [["AIR_BASIC", "P-CREW", "BASE-01", 2, None]]
    assert one_table(tables, "ProblemDescription")["instances"][0]["rows"] == [[delta["allowed_changes_exactly"][0]["from"]]]
    assert len([t for t in tables if any(i["rows"] for i in t["instances"])]) == 21
    assert len(delta["all_null_placeholder_tables"]) == 11
    assert all(not one_table(tables, name)["instances"][0]["rows"] for name in delta["all_null_placeholder_tables"])
    fixed = contract["source_fixed_context"]
    assert fixed["MissionType"]["TFOUT_fraction"] == fixed["MissionType"]["TFRET_fraction"] == .25
    assert fixed["MissionType"]["DURN_hours"] == 1.0
    assert fixed["OperationProfile_hours"] == [8.0, 20.0]
    assert contract["falsifiable_child_hypothesis"]["terminal_h36"] == {
        "local_P_Crew_booked": 0, "local_P_Crew_free": 1,
        "local_P_Crew_nominal": 1, "local_P_Crew_physical": 1,
        "outside_completed": 1, "ready_aircraft": 2, "transfer_pending": 0,
    }
    assert "transfer time0" in contract["falsifiable_child_hypothesis"]["h6"]
    assert "No h10 arrival" in contract["falsifiable_child_hypothesis"]["h6"]

    pcontract = json.loads((PARENT / "contract.json").read_text(encoding="utf-8"))
    report = contract["report_gate"]
    assert report["cells_per_arm"] == 5210
    for key in ("tables_in_order", "topology", "system_field_classes", "source_event_integrals_aircraft_hours", "source_event_counts", "stock_fields", "resource_fields", "result_summary_expected"):
        assert typed(report[key], pcontract["report_gate"][key]), key
    assert len(report["topology"]) == 6
    assert sum(len(t["columns"]) * t["rows"] for t in report["topology"]) == 5210
    assert len(report["resource_fields"]["total_expected_float32"]) == 5
    for key, value in report["resource_fields"]["total_expected_float32"].items():
        numerator = {"NR": 42, "NRA": 42, "NRN": 42, "NRUM": 2, "NRW": 1}[key]
        assert math.isfinite(value) and value == binary32(numerator / 36)
    assert "5,209" in report["full_cell_oracle"] and "5,210" in report["full_cell_oracle"]
    assert "no tolerance" in report["numeric_comparison"]["time_averaged_ResourceResultsTotal_dynamic_fields"]
    assert report["unknown_formula_or_unexplained_cell"] == "NO_GO; presentation constants have named bounded status and may not be claimed as statistical formula validation"
    assert contract["native_and_provenance_gate"]["status"] == "future, not native authorization from this contract alone"
    print(json.dumps({"decision": "PASS_CONTRACT_PINS_AND_GATES", "base": BASE, "contract_sha256": CONTRACT_SHA, "counts": counts, "report_cells_per_arm": 5210, "five_means_exact_binary32": True, "catalog_prefix_rule": True}, sort_keys=True))


if __name__ == "__main__":
    main()
