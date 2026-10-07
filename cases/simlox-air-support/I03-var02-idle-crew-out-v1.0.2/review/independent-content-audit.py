"""Read-only independent byte and scope audit of the frozen publication index."""

import hashlib
import json
import subprocess
from pathlib import Path


PKG = Path(__file__).resolve().parent.parent
REPO = PKG.parents[2]
INDEX = PKG / "evidence-index.json"
INDEX_SHA = "57d5ebba2f372f7f07ef092e5c2de58a5577988ade19587f13e522e3706339d8"
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


def doc(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"), object_pairs_hook=pairs)


def main() -> None:
    assert sha(INDEX.read_bytes()) == INDEX_SHA
    index = doc(INDEX)
    assert index["schema"] == "i03-var02-idle-out-evidence-index/v1"
    assert index["publication_id"] == "I03.var02.idle_crew_out.1.0.2"
    assert index["publication_state"] == "reusable_published"
    assert index["bounded_decision"] == "GO_BOUNDED_ONE_NATIVE_CHILD_AND_REUSED_BUSY_PARENT"
    assert index["new_native_runs"] == 1 and index["accepted_parent_runs_repeated"] == 0
    assert index["parent_report_cells"] == index["child_report_cells"] == 5210
    assert index["independent_checks"] == 14996
    assert index["source"] == index["source_files"]
    sources = index["source_files"]
    assert len(sources) == index["source_count"] == 170
    paths = [item["path"] for item in sources]
    assert len(set(paths)) == len(paths)
    assert all(not Path(path).is_absolute() and ".." not in Path(path).parts for path in paths)
    for item in sources:
        pin(PKG / item["path"], item)
        assert not item["path"].startswith("runs/")
    present = set()
    for path in PKG.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(PKG).as_posix()
        if relative == "evidence-index.json" or relative.startswith("runs/") or "/__pycache__/" in f"/{relative}/" or path.suffix == ".pyc":
            continue
        if relative.startswith(EXCLUDED):
            continue
        present.add(relative)
    assert set(paths) == present, sorted(present - set(paths))
    assert "review/independent-postrun-go-2026-10-07.md" in paths
    assert "review/independent-postrun-verdict-v3.json" in paths
    assert "review/independent-prelaunch-transport-supplement-2026-10-07.md" in paths
    assert "preserved-postrun-context/i03-var02-v102-actual-preflight-failure-20261007.json" in paths
    assert "review/independent-method-v1-no-go-2026-10-07.md" in paths
    assert "review/independent-method-v2-no-go-2026-10-07.md" in paths

    refs = index["accepted_source_refs"]
    assert len(refs) == 20 and len({r["path"] for r in refs}) == 20
    for item in refs:
        path = (PKG / item["path"]).resolve()
        assert path.is_relative_to(REPO)
        pin(path, item["local_disk"])
        git_path = path.relative_to(REPO).as_posix()
        blob = subprocess.check_output(["git", "show", f"{index['source_base_commit']}:{git_path}"], cwd=REPO)
        assert len(blob) == item["published_git_at_base"]["bytes"]
        assert sha(blob) == item["published_git_at_base"]["sha256"]
    installed = index["installed"]
    assert len(installed) == 3
    for item in installed:
        pin(Path(item["path"]), item)

    raw = index["raw_files"]
    assert len(raw) == index["raw_record_count"] == 59
    assert len({item["original_path"] for item in raw}) == 59
    assert sum(item["role"] == "accepted_busy_parent_or_dependency" for item in raw) == 34
    assert sum(item["role"].startswith("sealed_v102_child") for item in raw) == 25
    for item in raw:
        pin(Path(item["original_path"]), item)
    context = index["postrun_context_copies"]
    assert len(context) == 19
    for item in context:
        pin(PKG / item["copy_path"], item)
        original = REPO / item["original_path"]
        if original.exists():
            pin(original, item)
    historical = index["historical_unpublished_copies"]
    assert len(historical) == 26
    for item in historical:
        pin(PKG / item["copy_path"], item)
        original = REPO / item["original_path"]
        if original.exists():
            pin(original, item)
    catalog = index["catalog_history"]
    archive = PKG / catalog["owned_archive"]
    pin(archive, catalog["local_disk_at_selection"])
    archived_doc = doc(archive)
    live = doc(REPO / catalog["path"])
    assert len(archived_doc["entries"]) == catalog["entry_count_at_selection"] == 490
    assert live["entries"][:490] == archived_doc["entries"]
    assert {k: v for k, v in live.items() if k != "entries"} == {k: v for k, v in archived_doc.items() if k != "entries"}
    base_blob = subprocess.check_output(["git", "show", f"{index['source_base_commit']}:{catalog['path']}"], cwd=REPO)
    assert len(base_blob) == catalog["published_git_at_base"]["bytes"]
    assert sha(base_blob) == catalog["published_git_at_base"]["sha256"]

    entry = doc(PKG / "publication-entry.json")
    assert entry["publication_id"] == index["publication_id"]
    assert entry["bounded_decision"] == index["bounded_decision"]
    assert entry["new_native_runs"] == 1 and entry["accepted_parent_runs_repeated"] == 0
    assert entry["evidence_index"] == f"{PKG.name}/evidence-index.json"
    for key in ("contract", "evidence", "readme", "reproduction_guide", "signoff", "evidence_index"):
        target = (PKG.parent / entry[key]).resolve()
        assert target.is_file() and target.is_relative_to(PKG)
    print(json.dumps({"schema": "i03-var02-independent-content-audit/v1",
                      "decision": "GO_CONTENT_BYTES_AND_SCOPE",
                      "index_sha256": INDEX_SHA,
                      "source": len(sources), "accepted_dual": len(refs),
                      "raw": len(raw), "context_copies": len(context),
                      "historical_copies": len(historical), "installed": len(installed),
                      "catalog_prior_entries": 490}, sort_keys=True))


if __name__ == "__main__":
    main()
