"""Independent read-only staged Git/blob audit; excluded from evidence index."""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[4]
INDEX = PACKAGE / "evidence-index.json"
CATALOG = REPO / "cases/simlox-air-support/publication-index-v1.json"
OLD = REPO / "tmp/publication-index-before-c09-var02-control-v011-20261007.json"
INDEX_SHA = "c76f768942de24e9733e61e5dcf44755430fe5b910593f842710588536d3ff50"


def git_bytes(revision: str, path: str) -> bytes:
    result = subprocess.run(["git", "show", f"{revision}:{path}"], cwd=REPO,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    return result.stdout


def digest(raw: bytes) -> dict:
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def repo_path(path: Path) -> str:
    return path.resolve().relative_to(REPO).as_posix()


def main() -> None:
    assert digest(INDEX.read_bytes())["sha256"] == INDEX_SHA
    index = json.loads(INDEX.read_text(encoding="utf-8"))
    assert index["source_count"] == 101 and index["raw_count"] == 130
    source_paths = set()
    for record in index["source_files"]:
        path = (PACKAGE / record["path"]).resolve()
        relative = repo_path(path)
        assert digest(path.read_bytes()) == digest(git_bytes("", relative)) == {
            "bytes": record["bytes"], "sha256": record["sha256"]}, relative
        assert "/runs/" not in relative
        source_paths.add(relative)
    assert len(source_paths) == 101
    index_path = repo_path(INDEX)
    assert digest(git_bytes("", index_path))["sha256"] == INDEX_SHA
    assert INDEX.read_bytes() == git_bytes("", index_path)

    excluded = [PACKAGE / "review/independent-content-go-2026-10-07.md",
                PACKAGE / "review/independent-publication-content-audit.py"]
    for path in excluded:
        relative = repo_path(path)
        assert relative not in source_paths
        assert path.read_bytes() == git_bytes("", relative)
    catalog_path = repo_path(CATALOG)
    expected_paths = source_paths | {index_path, catalog_path} | {repo_path(path) for path in excluded}
    staged = subprocess.run(["git", "diff", "--cached", "--name-only", "-z"], cwd=REPO,
                            stdout=subprocess.PIPE, check=True).stdout.decode("utf-8").split("\0")
    staged = {path for path in staged if path}
    assert staged == expected_paths, (len(staged), staged - expected_paths, expected_paths - staged)
    assert len(staged) == 105

    for record in index["raw_files"]:
        path = (PACKAGE / record["path"]).resolve()
        assert digest(path.read_bytes()) == {"bytes": record["bytes"], "sha256": record["sha256"]}, path
    base = index["accepted_source_base_commit"]
    distinct = 0
    for record in index["accepted_source_refs"]:
        path = (PACKAGE / record["path"]).resolve()
        assert digest(path.read_bytes()) == record["local_disk"], path
        assert digest(git_bytes(base, repo_path(path))) == record["published_git"], path
        distinct += record["local_disk"] != record["published_git"]
    assert len(index["accepted_source_refs"]) == 77 and distinct == 2

    old_disk = OLD.read_bytes()
    old_git = git_bytes("HEAD", catalog_path)
    new_disk = CATALOG.read_bytes()
    new_git = git_bytes("", catalog_path)
    parse = lambda raw: json.loads(raw.decode("utf-8-sig"))
    old = parse(old_disk)
    old_head = parse(old_git)
    new = parse(new_disk)
    new_stage = parse(new_git)
    assert old == old_head
    assert new == new_stage
    assert len(old["entries"]) == 485 and len(new["entries"]) == 486
    assert new["entries"][:485] == old["entries"]
    assert {k: new[k] for k in new if k != "entries"} == {k: old[k] for k in old if k != "entries"}
    entry = json.loads((PACKAGE / "publication-entry-v1.json").read_text(encoding="utf-8"))
    assert new["entries"][-1] == entry
    assert len({x["publication_id"] for x in new["entries"]}) == 486
    assert entry["positive_pair_accepted"] is False and entry["new_native_runs"] == 0
    assert entry["original_pair_decision"] == "NO_GO_PROSPECTIVE_PAIR"
    assert entry["shortage_arm"] == "not_started_not_tested"
    print(json.dumps({"passed": True, "staged_paths": 105, "indexed_sources": 101,
                      "raw_seals": 130, "accepted_source_git_refs": 77,
                      "distinct_local_git_refs": distinct, "catalog_old_entries": 485,
                      "catalog_new_entries": 486, "catalog_old_disk": digest(old_disk),
                      "catalog_old_git": digest(old_git), "catalog_new_disk": digest(new_disk),
                      "catalog_new_staged_git": digest(new_git)}, sort_keys=True))


if __name__ == "__main__":
    main()
