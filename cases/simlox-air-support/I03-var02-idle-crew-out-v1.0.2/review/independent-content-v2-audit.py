"""Independent, read-only audit of the append-aware I03 publication index."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path


PKG = Path(__file__).resolve().parent.parent
REPO = PKG.parents[2]
INDEX_SHA = "4060de5d7434ff675949b9eea7fb8f827ac0c72a56e530169b60ecb0da0724dc"
OLD_SHA = "57d5ebba2f372f7f07ef092e5c2de58a5577988ade19587f13e522e3706339d8"
OLD_REVIEW = {"review/independent-content-audit.py",
              "review/independent-content-go-2026-10-08.md",
              "review/independent-publication-v1-no-go-audit.py",
              "review/independent-publication-v1-no-go-2026-10-08.md"}
EXCLUDED = ("review/independent-content", "review/independent-staged",
            "review/independent-remote", "review/independent-publication",
            "review/independent-pr-")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def pin(path: Path, record: dict) -> None:
    data = path.read_bytes()
    assert len(data) == record["bytes"] and sha(data) == record["sha256"], path


def pairs(items):
    result = {}
    for key, value in items:
        assert key not in result, key
        result[key] = value
    return result


def doc(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=pairs)


def main() -> None:
    index_path = PKG / "evidence-index-v2.json"
    assert sha(index_path.read_bytes()) == INDEX_SHA
    assert sha((PKG / "evidence-index.json").read_bytes()) == OLD_SHA
    index = doc(index_path)
    assert index["schema"] == "i03-var02-idle-out-evidence-index/v2"
    assert index["publication_id"] == "I03.var02.idle_crew_out.1.0.2"
    assert index["bounded_decision"] == "GO_BOUNDED_WITH_POSTAPPEND_REPLAY_REPAIR_V2"
    assert index["v1_index_sha256"] == OLD_SHA
    assert index["v1_publication_replay_decision"] == "NO_GO_PUBLICATION_REPRO_V1"
    assert index["independent_checks_at_original_acceptance"] == 14996
    assert index["independent_checks_after_catalog_append"] == 14995
    assert index["conditional_prepublication_catalog_check_not_applicable"] == 1
    assert index["all_other_independent_verdict_fields_type_exact_equal"] is True
    assert index["parent_report_cells"] == index["child_report_cells"] == 5210
    assert index["new_native_runs"] == 1 and index["accepted_parent_runs_repeated"] == 0
    assert index["source"] == index["source_files"]
    sources = index["source_files"]
    assert len(sources) == index["source_count"] == 192
    paths = [record["path"] for record in sources]
    assert len(set(paths)) == len(paths)
    for record in sources:
        path = Path(record["path"])
        assert not path.is_absolute() and ".." not in path.parts
        assert not record["path"].startswith("runs/")
        pin(PKG / path, record)
    expected = set()
    for path in PKG.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(PKG).as_posix()
        if relative == "evidence-index-v2.json" or relative.startswith("runs/") or "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        if relative.startswith(EXCLUDED) and relative not in OLD_REVIEW:
            continue
        expected.add(relative)
    assert set(paths) == expected, sorted(expected - set(paths))
    for required in ("evidence-index.json", "make_evidence_index.py",
                     "review/independent-publication-v1-no-go-audit.py",
                     "review/independent-publication-v1-no-go-2026-10-08.md",
                     "review/independent-content-audit.py",
                     "review/independent-content-go-2026-10-08.md",
                     "review/independent-postrun-verdict-v3.json"):
        assert required in paths, required

    refs = index["accepted_source_refs"]
    assert len(refs) == 20 and len({r["path"] for r in refs}) == 20
    for record in refs:
        path = (PKG / record["path"]).resolve()
        assert path.is_relative_to(REPO)
        pin(path, record["local_disk"])
        blob = subprocess.check_output(["git", "show", f"{index['source_base_commit']}:{path.relative_to(REPO).as_posix()}"], cwd=REPO)
        assert len(blob) == record["published_git_at_base"]["bytes"]
        assert sha(blob) == record["published_git_at_base"]["sha256"]
    assert len(index["installed"]) == 3
    for record in index["installed"]:
        pin(Path(record["path"]), record)
    raw = index["raw_files"]
    assert len(raw) == index["raw_record_count"] == 59
    assert len({r["original_path"] for r in raw}) == 59
    for record in raw:
        pin(Path(record["original_path"]), record)
    for key, count in (("postrun_context_copies", 19),
                       ("postappend_failure_copies", 8),
                       ("historical_unpublished_copies", 26)):
        records = index[key]
        assert len(records) == count
        for record in records:
            pin(PKG / record["copy_path"], record)
            original = REPO / record["original_path"]
            if original.exists():
                pin(original, record)

    catalog = index["catalog_history"]
    archive = PKG / catalog["owned_archive"]
    pin(archive, catalog["local_disk_at_selection"])
    old_catalog = doc(archive)
    live = doc(REPO / catalog["path"])
    assert len(old_catalog["entries"]) == 490 and len(live["entries"]) >= 491
    assert live["entries"][:490] == old_catalog["entries"]
    assert {k: v for k, v in live.items() if k != "entries"} == {k: v for k, v in old_catalog.items() if k != "entries"}
    blob = subprocess.check_output(["git", "show", f"{index['source_base_commit']}:{catalog['path']}"], cwd=REPO)
    assert len(blob) == catalog["published_git_at_base"]["bytes"]
    assert sha(blob) == catalog["published_git_at_base"]["sha256"]
    entry = doc(PKG / "publication-entry-v2.json")
    assert entry["publication_id"] == index["publication_id"]
    assert entry["evidence_index"] == f"{PKG.name}/evidence-index-v2.json"
    assert entry["bounded_decision"] == index["bounded_decision"]
    for key in ("contract", "evidence", "readme", "reproduction_guide", "signoff", "evidence_index"):
        target = (PKG.parent / entry[key]).resolve()
        assert target.is_file() and target.is_relative_to(PKG)
    original = doc(PKG / "review/independent-postrun-verdict-v3.json")
    replay = subprocess.run([sys.executable, "-X", "utf8", "-B", str(PKG / "review/independent_replay_v3.py")], cwd=REPO, capture_output=True, check=True)
    assert replay.stderr == b""
    current = json.loads(replay.stdout.decode("utf-8-sig"), object_pairs_hook=pairs)
    assert original["checks"] == 14996 and current["checks"] == 14995
    assert {k: v for k, v in original.items() if k != "checks"} == {k: v for k, v in current.items() if k != "checks"}
    print(json.dumps({"schema": "i03-var02-independent-content-v2-audit/v1",
                      "decision": "GO_CONTENT_V2_BYTES_AND_SCOPE", "index_sha256": INDEX_SHA,
                      "source": len(sources), "raw": len(raw), "accepted_dual": len(refs),
                      "postrun_context": 19, "postappend_failure_copies": 8,
                      "historical_copies": 26, "installed": 3,
                      "native_acceptance_checks": 14996, "postappend_checks": 14995}, sort_keys=True))


if __name__ == "__main__":
    main()
