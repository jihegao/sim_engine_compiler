"""Deterministic postrun evidence index; default and --dry never write."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

from build import typed_equal
from make_raw_custody import candidate as raw_candidate
from postrun_audit import replay as author_replay
from postrun_context import verify as context_verify
from review_proof_context import check as review_proof_verify

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
INDEX = HERE / "evidence-index.json"
MANIFEST = HERE / "prelaunch-manifest.json"
RUN = HERE / "runs/i03-var11-out-unarrived-v100-ssh-20261008-01"
PYTHON = Path(sys.executable)
PUBLICATION_ID = "I03.var11.out_unarrived_horizon.1.0.0"
CONTRACT_SHA = "67bef26d4fdec4d34e88b20e177239fb973aeba7152f72d26d4d9f9a4f9a79c1"
MANIFEST_SHA = "4aa438b946ff43b2e76f21eb1888f50ee976d1444cb568e5f52c13917f7703fe"
APPROVED_READER_SHA = "08e64f0095a9cedfea45a4253418c844bf64c66aa15a4790b665ee4cde740170"
REPAIRED_READER_SHA = "381bc37e89b6ebfc6a0b3d0cc35752d1a29f42beb5ac739752ee8a97675f7cf0"
REPAIRED_VERDICT_SHA = "fa7c577ba115340d4d153390e2408a5970adeff871cc20ade99e77e4a2be30fc"
REPAIRED_MEMO_SHA = "088359633ead06d772c457e8d4c0f13b55246a58181c65f2660dc175a82af516"
ORIGINAL_NO_GO_SHA = "947bb723a61883887e15d0019013b9f919fc32552920345aefde1b8ec68225af"

ADDITIONAL_FILES = (
    "prelaunch-manifest.json",
    "postrun_context.py", "postrun-context-custody.json",
    "review_proof_context.py", "independent-postrun-proof-custody.json",
    "make_raw_custody.py", "raw-custody-map.json",
    "postrun_audit.py", "author-postrun-verdict.json",
    "make_evidence_index.py", "README-publication.md", "REPRODUCTION-postrun.md",
    "cli-scope-signoff-2026-10-08.md", "publication-entry.json",
    "preserved-postrun-development/postrun-audit-tuple-json-draft.py.bytes",
    "review/preflight-ssh0-20261007T210756239Z.json",
    "review/independent-prelaunch-go.json",
    "review/independent-prelaunch-go-2026-10-08.md",
    "review/independent_replay_v2.py",
    "review/independent-postrun-verdict-v2.json",
    "review/independent-postrun-go-v2-2026-10-08.md",
    "review/independent-postrun-v1-no-go-2026-10-08.md",
)
EXCLUDED_REVIEW_PREFIXES = (
    "review/independent-content", "review/independent-staged",
    "review/independent-remote", "review/independent-pr-",
)


def pin(path: Path) -> dict:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def additional_owned() -> list[str]:
    paths = list(ADDITIONAL_FILES)
    for mapping in ("postrun-context-custody.json", "independent-postrun-proof-custody.json"):
        rows = json.loads((HERE / mapping).read_text(encoding="utf-8"))["records"]
        paths.extend(row["owned_copy"] for row in rows)
    assert len(paths) == len(set(paths))
    return paths


def source_inventory() -> list[dict]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8-sig"))
    old_owned = [Path(row["path"]).relative_to(HERE).as_posix()
                 for row in manifest["source_files"] if Path(row["path"]).is_relative_to(HERE)]
    assert len(old_owned) == 175
    names = set(old_owned) | set(additional_owned())
    assert len(names) == len(old_owned) + len(additional_owned())
    assert "evidence-index.json" not in names
    all_files = {p.relative_to(HERE).as_posix() for p in HERE.rglob("*") if p.is_file()
                 and not any(part in {"runs", "transport-evidence", "test-output", "__pycache__"}
                             for part in p.relative_to(HERE).parts)
                 and p.name != "evidence-index.json"
                 and not any(p.relative_to(HERE).as_posix().startswith(prefix)
                             for prefix in EXCLUDED_REVIEW_PREFIXES)}
    assert names == all_files, {"unindexed": sorted(all_files - names),
                                "missing": sorted(names - all_files)}
    return [{"path": name, **pin(HERE / name)} for name in sorted(names)]


def independent_replay() -> dict:
    assert pin(HERE / "review/independent_replay.py")["sha256"] == APPROVED_READER_SHA
    assert pin(HERE / "review/independent_replay_v2.py")["sha256"] == REPAIRED_READER_SHA
    assert pin(HERE / "review/independent-postrun-verdict-v2.json")["sha256"] == REPAIRED_VERDICT_SHA
    assert pin(HERE / "review/independent-postrun-go-v2-2026-10-08.md")["sha256"] == REPAIRED_MEMO_SHA
    assert pin(HERE / "review/independent-postrun-v1-no-go-2026-10-08.md")["sha256"] == ORIGINAL_NO_GO_SHA
    result = subprocess.run([str(PYTHON), "-X", "utf8", "-B",
                             str(HERE / "review/independent_replay_v2.py")],
                            cwd=REPO, capture_output=True)
    assert type(result.returncode) is int and result.returncode == 0 and result.stderr == b""
    current = json.loads(result.stdout)
    frozen = json.loads((HERE / "review/independent-postrun-verdict-v2.json").read_text(encoding="utf-8"))
    proof = json.loads((HERE / "independent-postrun-proof-custody.json").read_text(encoding="utf-8"))["records"]
    stdout_rows = [r for r in proof if r["original"].endswith("/replay.stdout.bin")]
    assert len(stdout_rows) == 1
    original = json.loads((HERE / stdout_rows[0]["owned_copy"]).read_bytes())
    assert typed_equal(current, original) and typed_equal(current, frozen)
    assert current["checks"] == 18550
    assert current["status"] == "GO_BOUNDED_IF_ORIGINAL_RUN_SEALED"
    assert current["parent_report_cells"] == current["child_report_cells"] == 5210
    assert current["paired_non_description_cells"] == 5209
    return frozen


def build() -> dict:
    assert pin(HERE / "contract.json")["sha256"] == CONTRACT_SHA
    assert pin(MANIFEST)["sha256"] == MANIFEST_SHA
    assert (HERE / ".gitattributes").read_bytes() == b"* -text\n"
    author = author_replay()  # exact source/raw/catal og prefix remains mandatory
    assert typed_equal(author, json.loads((HERE / "author-postrun-verdict.json").read_text(encoding="utf-8")))
    assert author["decision"] == "GO_AUTHOR_SEALED_REPLAY_ONLY"
    assert context_verify()["records"] == 32
    assert review_proof_verify()["records"] == 9
    independent = independent_replay()
    raw = raw_candidate()["records"]
    saved_raw = json.loads((HERE / "raw-custody-map.json").read_text(encoding="utf-8"))["records"]
    assert typed_equal(raw, saved_raw) and len(raw) == 169
    entry = json.loads((HERE / "publication-entry.json").read_text(encoding="utf-8"))
    assert entry["publication_id"] == PUBLICATION_ID
    assert entry["evidence_index"] == f"{HERE.name}/evidence-index.json"
    assert entry["publication_state"] == "reusable_published"
    assert entry["new_native_runs"] == 1 and entry["accepted_parent_runs_repeated"] == 0
    contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
    lineage = contract["source_lineage"]
    source = source_inventory()
    assert len({r["path"] for r in source}) == len(source)
    return {
        "schema": "i03-var11-out-unarrived-evidence-index/v1",
        "publication_id": PUBLICATION_ID, "case_id": "I03", "variant_id": "I03.var11", "version": "1.0.0",
        "publication_state": "reusable_published_after_reviewed_catalog_merge",
        "bounded_decision": "GO_BOUNDED_ORIGINAL_RUN_WITH_VERSIONED_READER_REPAIR",
        "approved_v1_reader_postrun_decision": "NO_GO_METHOD",
        "new_native_runs": 1, "accepted_parent_runs_repeated": 0,
        "run_id": RUN.name, "contract_sha256": CONTRACT_SHA,
        "prelaunch_manifest_sha256": MANIFEST_SHA,
        "approved_v1_reader_sha256": APPROVED_READER_SHA,
        "repaired_v2_reader_sha256": REPAIRED_READER_SHA,
        "repaired_independent_verdict_sha256": REPAIRED_VERDICT_SHA,
        "independent_checks": independent["checks"],
        "parent_report_cells": independent["parent_report_cells"],
        "child_report_cells": independent["child_report_cells"],
        "paired_non_description_cells": independent["paired_non_description_cells"],
        "terminal_started_unarrived_task_quantity": independent["terminal_unarrived_task_quantity"],
        "terminal_completed_out_task_quantity": author["terminal_completed_out_task_quantity"],
        "source_base_commit": lineage["base_commit"],
        "source_count": len(source), "source": source, "source_files": source,
        "accepted_source_refs": lineage["primary_parent_source_and_secondary_context_source_disk_vs_git_at_base"],
        "raw_record_count": len(raw), "raw_files": raw,
        "prelaunch_source_record_count": 782,
        "small_postrun_context": json.loads((HERE / "postrun-context-custody.json").read_text(encoding="utf-8"))["records"],
        "independent_proof_context": json.loads((HERE / "independent-postrun-proof-custody.json").read_text(encoding="utf-8"))["records"],
        "catalog_history": {
            "owned_exact_archive": lineage["catalog_at_selection"]["owned_exact_archive"],
            "local_disk_at_selection": lineage["catalog_at_selection"]["local_disk"],
            "published_git_at_base": lineage["catalog_at_selection"]["published_git_at_base"],
            "required_prefix_entries": 492,
            "sealed_policy": "exact owned archive and base Git blob; current catalog type-exact metadata, first 492 entries and unique appended publication IDs always checked",
        },
        "raw_location_policy": "All 144 prior raw and 25 child run records are mandatory at their original paths; no copy substitution or rerun.",
        "source_location_policy": "Exact package source bytes under * -text; no native binary, native raw run, or transport-evidence directory is published.",
        "limits": [
            "Fixed source, seed, executable and h36 horizon; h46 is arithmetic only, not observed.",
            "Started-but-unarrived is task quantity, not persistent person/outside-pool or report transit display.",
            "Five System zero fields and empty-stock PNB/null are bounded presentation conventions, not general formulas.",
            "Original approved reader failure remains NO_GO_METHOD; v2 repair changed only its finite numeric h6 receipt presentation gate and historical v1 SHA binding.",
            "No general OUT TFDT, GUI, performance, cross-engine or whole-I03 claim.",
        ],
    }


def main() -> None:
    assert sys.argv[1:] in ([], ["--dry"], ["--write"])
    doc = build()
    raw = (json.dumps(doc, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()
    if sys.argv[1:] == ["--write"]:
        assert not INDEX.exists(), "preserve an existing evidence index"
        INDEX.write_bytes(raw)
    elif sys.argv[1:] == []:
        assert INDEX.is_file() and INDEX.read_bytes() == raw
    print(json.dumps({"schema": "i03-var11-index-check/v1", "passed": True,
                      "source_count": len(doc["source_files"]), "raw_count": len(doc["raw_files"]),
                      "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest(),
                      "written": sys.argv[1:] == ["--write"]}, separators=(",", ":")))


if __name__ == "__main__":
    main()
