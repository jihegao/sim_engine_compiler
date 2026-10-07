"""Deterministic, read-only I03.var02 evidence index builder; --write creates once."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from make_raw_custody import build as raw_custody_check
from postrun_audit import audit as author_audit
from postrun_context import custody as context_check
from verify_sources import HERE, REPO, identity, strict_equal, verify


INDEX = HERE / "evidence-index.json"
MANIFEST = HERE / "prelaunch-manifest-v2.json"
CONTRACT_SHA = "1f058ae8706d4de81c28099b6580619eb4cb879e20314619f387839d9150ee29"
MANIFEST_SHA = "fa803d4b0dc7746e4ae3e72288dcdb2cc1a3d3334ca6e5adcb2df8fcb2de1da6"
INDEPENDENT_METHOD_SHA = "e8a249c11df2f90f08e838f854432a27eeffacae5b814ceeb16ab4c00ad27e6e"
INDEPENDENT_VERDICT_SHA = "67265c50b84e1ea1c325914e5ecd4988e58a2548e1fbe02b4ca2340d143a13c6"
INDEPENDENT_MEMO_SHA = "307768e9f997636d46708eed18be3592e1a62d80248390d88a73406c14491659"
EXCLUDED_REVIEW_PREFIXES = (
    "review/independent-content", "review/independent-staged", "review/independent-remote",
    "review/independent-publication", "review/independent-pr-",
)


def pin(path: Path) -> dict:
    return identity(path.read_bytes())


def exact(path: Path, expected: dict) -> None:
    assert pin(path) == {key: expected[key] for key in ("bytes", "sha256")}, str(path)


def build() -> dict:
    assert pin(HERE / "contract.json")["sha256"] == CONTRACT_SHA
    assert pin(MANIFEST)["sha256"] == MANIFEST_SHA
    assert (HERE / ".gitattributes").read_bytes() == b"* -text\n"
    assert pin(HERE / "review/independent_replay_v3.py")["sha256"] == INDEPENDENT_METHOD_SHA
    assert pin(HERE / "review/independent-postrun-verdict-v3.json")["sha256"] == INDEPENDENT_VERDICT_SHA
    assert pin(HERE / "review/independent-postrun-go-2026-10-07.md")["sha256"] == INDEPENDENT_MEMO_SHA
    assert context_check()["byte_identical_copies"] == 19
    assert raw_custody_check(False)["records"] == 59
    assert verify("sealed", MANIFEST)["passed"] is True
    author = author_audit()
    assert strict_equal(author, json.loads((HERE / "author-postrun-verdict.json").read_text(encoding="utf-8")))
    assert author["decision"] == "GO_AUTHOR_SEALED_REPLAY" and author["report_cells_checked_child"] == 5210
    independent = json.loads((HERE / "review/independent-postrun-verdict-v3.json").read_text(encoding="utf-8"))
    replay = subprocess.run([sys.executable, "-X", "utf8", "-B", str(HERE / "review/independent_replay_v3.py")],
                            cwd=REPO, capture_output=True)
    assert replay.returncode == 0 and not replay.stderr, replay.stderr.decode("utf-8", "replace")
    assert strict_equal(independent, json.loads(replay.stdout.decode("utf-8-sig")))
    assert independent["status"] == "GO_BOUNDED"
    assert independent["checks"] == 14996
    assert independent["parent_report_cells"] == independent["child_report_cells"] == 5210
    assert independent["native_raw_files"] == 23 and independent["native_steps"] == 6

    contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
    assert contract["case_id"] == "I03" and contract["variant_id"] == "I03.var02"
    assert contract["run_id"] == author["run_id"]
    base = contract["ownership"]["base_commit"]
    accepted_refs = []
    for item in contract["source_lineage"]["accepted_source_local_vs_published_git_at_base"]:
        original = REPO / item["path"]
        exact(original, item["local_disk"])
        blob = subprocess.check_output(["git", "show", f"{base}:{item['path']}"], cwd=REPO)
        assert identity(blob) == item["published_git_at_base"]
        accepted_refs.append({"path": Path(os.path.relpath(original, HERE)).as_posix(),
                              "local_disk": item["local_disk"],
                              "published_git_at_base": item["published_git_at_base"]})
    assert len(accepted_refs) == 20
    installed = []
    for role, item in contract["source_lineage"]["installed"].items():
        exact(Path(item["path"]), item)
        installed.append({"role": role, "path": item["path"], **{k: item[k] for k in ("bytes", "sha256")}})
    assert len(installed) == 3

    raw = json.loads((HERE / "raw-custody-map.json").read_text(encoding="utf-8"))["records"]
    context = json.loads((HERE / "postrun-context-custody.json").read_text(encoding="utf-8"))["records"]
    historic = []
    lineage = contract["source_lineage"]
    for section in ("excluded_v100_NO_GO_files", "excluded_v101_NO_GO_files", "owned_historical_root_context"):
        for item in lineage[section]:
            exact(HERE / item["owned_inert_copy"], item)
            original = REPO / item["original_path"]
            if original.exists():
                exact(original, item)
            historic.append({"section": section, "original_path": item["original_path"],
                             "copy_path": item["owned_inert_copy"],
                             "bytes": item["bytes"], "sha256": item["sha256"]})
    assert len(historic) == 26
    source = []
    for path in sorted(HERE.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(HERE).as_posix()
        if rel == INDEX.name or "__pycache__" in path.parts or path.suffix == ".pyc" or "/runs/" in f"/{rel}/":
            continue
        if rel.startswith(EXCLUDED_REVIEW_PREFIXES):
            continue
        source.append({"path": rel, **pin(path)})
    assert len({item["path"] for item in source}) == len(source)
    assert all((HERE / item["path"]).is_file() for item in source)
    assert all(not item["path"].startswith("runs/") for item in source)
    entry = json.loads((HERE / "publication-entry.json").read_text(encoding="utf-8"))
    assert entry["publication_id"] == "I03.var02.idle_crew_out.1.0.2"
    assert entry["evidence_index"] == "I03-var02-idle-crew-out-v1.0.2/evidence-index.json"
    catalog = lineage["catalog_at_selection"]
    assert pin(HERE / catalog["owned_exact_archive"]) == catalog["owned_archive_pin"]
    return {
        "schema": "i03-var02-idle-out-evidence-index/v1",
        "publication_id": entry["publication_id"],
        "case_id": "I03", "variant_id": "I03.var02", "version": "1.0.2",
        "publication_state": "reusable_published",
        "bounded_decision": "GO_BOUNDED_ONE_NATIVE_CHILD_AND_REUSED_BUSY_PARENT",
        "contract_sha256": CONTRACT_SHA,
        "prelaunch_manifest_sha256": MANIFEST_SHA,
        "source_base_commit": base,
        "run_id": contract["run_id"],
        "new_native_runs": 1, "accepted_parent_runs_repeated": 0,
        "author_method_sha256": pin(HERE / "postrun_audit.py")["sha256"],
        "independent_method_sha256": INDEPENDENT_METHOD_SHA,
        "parent_report_cells": 5210, "child_report_cells": 5210,
        "independent_checks": 14996, "child_typed_event_records": 177,
        "child_raw_records": 23, "child_run_custody_records": 2,
        "source_count": len(source), "source": source, "source_files": source,
        "accepted_source_refs": accepted_refs, "installed": installed,
        "raw_record_count": len(raw), "raw_files": raw,
        "postrun_context_copies": context, "historical_unpublished_copies": historic,
        "catalog_history": {"path": catalog["path"], "owned_archive": catalog["owned_exact_archive"],
                            "local_disk_at_selection": catalog["local_disk"],
                            "published_git_at_base": catalog["published_git_at_base"],
                            "entry_count_at_selection": 490,
                            "sealed_replay_policy": "exact archive and base Git identities; current live catalog preserves metadata and first 490 entries and may append only"},
        "source_location_policy": "Package-relative publishable source pins use exact bytes and * -text; historical unpublished source originals have named inert copies. No binary or native raw is included.",
        "raw_location_policy": "The 34 accepted run records and 25 child run records remain mandatory at their original paths, with no substitute or rerun.",
        "limits": [
            "Fixed seed, BASE-01, one zero-duration P-CREW OUT unit, two aircraft and two waves only.",
            "Five System zero fields and empty-stock PNB/nulls are bounded native presentation, not general statistical formulas.",
            "No persistent individual crew identity, zero-availability, BETWEEN, equipment, batch, priority, shift/rest, GUI, performance, cross-engine or whole-I03 claim.",
            "v1.0.0/v1.0.1 contract, v1/v2 method and initial failed preflight artifacts remain excluded and unmodified.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true", help="create index once only when absent")
    args = parser.parse_args()
    doc = build()
    data = (json.dumps(doc, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    if args.write:
        with INDEX.open("xb") as stream:
            stream.write(data)
    elif INDEX.exists():
        assert INDEX.read_bytes() == data, "existing frozen index differs from strict dry build"
    print(json.dumps({"schema": "i03-var02-evidence-index-build/v1", "source_count": doc["source_count"],
                      "raw_count": doc["raw_record_count"], "bytes": len(data),
                      "sha256": hashlib.sha256(data).hexdigest(), "written": args.write}, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
