"""Read-only exact staged-byte gate for B03.var01 v0.1.2."""

import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
REPO = next(p for p in HERE.parents if (p / ".git").exists())
PKG = HERE.relative_to(REPO).as_posix()
CATALOG = "cases/simlox-air-support/publication-index-v1.json"
INDEX_SHA = "b0cae8348fa677c3d4ee1b0254f74361779cdede80ade1aebb49b64cb1caaf2a"
EXTRA = {
    "review/independent-content-audit.py": "4828c281191d36c33d5f691231f903f756a052b70b3eb6effb5c3000ef4ec012",
    "review/independent-content-go-2026-10-07.md": "385d4e4e54d05e908f552d120982f9a44c8ba3adf338f75ecd631b54e60c83c6",
    "review/independent-content-audit-key-draft.py": "f2ec4a1554cf5b705564e5549b1584c160a1cd7c2253d6d777b0a9f6b24b8c34",
    "review/independent-content-audit-installed-draft.py": "f619c8fd8bc147dbf9e467bafcdd19ec196096f8dc9c6ddfa08f4c7f077f31d3",
}


def git(*args):
    return subprocess.check_output(["git", *args], cwd=REPO)


def pin(data):
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def exact(path, record):
    data = path.read_bytes()
    assert pin(data) == {"bytes": record["bytes"], "sha256": record["sha256"]}, str(path)
    return data


def main():
    index_bytes = exact(HERE / "evidence-index.json", {"bytes": 116421, "sha256": INDEX_SHA})
    index = json.loads(index_bytes)
    assert index["source"] == index["source_files"] and len(index["source"]) == 129
    expected = {f"{PKG}/{record['path']}" for record in index["source"]}
    expected |= {f"{PKG}/{name}" for name in EXTRA}
    expected |= {f"{PKG}/evidence-index.json", CATALOG}
    staged = {x.decode("utf-8") for x in git("diff", "--cached", "--name-only", "-z").split(b"\0") if x}
    assert len(staged) == len(expected) == 135
    assert staged == expected, {"extra": sorted(staged - expected), "missing": sorted(expected - staged)}

    for record in index["source"]:
        rel = f"{PKG}/{record['path']}"
        raw = exact(REPO / rel, record)
        assert git("show", f":{rel}") == raw, rel
    assert git("show", f":{PKG}/evidence-index.json") == index_bytes
    for rel, digest in EXTRA.items():
        path = f"{PKG}/{rel}"
        raw = (REPO / path).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == digest
        assert git("show", f":{path}") == raw

    contract = json.loads((HERE / "contract.json").read_bytes())
    assert len(index["accepted_source_refs"]) == len(contract["accepted_source_files"]) == 38
    declared = {record["path"]: record for record in contract["accepted_source_files"]}
    for record in index["accepted_source_refs"]:
        target = (HERE / record["path"]).resolve()
        rel = target.relative_to(REPO).as_posix()
        assert record["local_disk"] == declared[rel]["local_disk"]
        assert record["published_git_at_base"] == declared[rel]["published_git_at_base"]
        exact(target, record["local_disk"])
        assert pin(git("show", f"{index['source_base_commit']}:{rel}")) == record["published_git_at_base"]
    assert len(index["raw_files"]) == 30 and len(index["context_copies"]) == 88
    for record in index["raw_files"]:
        exact(Path(record["original_path"]), record)
    for record in index["context_copies"]:
        copy = (HERE / record["copy_path"]).resolve()
        assert copy.is_relative_to(HERE)
        exact(copy, record)
        original = Path(record["original_path"])
        if original.exists():
            exact(original, record)
    for record in index["installed"]:
        exact(Path(record["path"]), record)

    old_blob = git("show", f"HEAD:{CATALOG}")
    staged_blob = git("show", f":{CATALOG}")
    disk_blob = (REPO / CATALOG).read_bytes()
    old, current = json.loads(old_blob), json.loads(staged_blob)
    assert json.loads(disk_blob) == current
    assert len(old["entries"]) == 489 and len(current["entries"]) == 490
    assert {k: v for k, v in old.items() if k != "entries"} == {k: v for k, v in current.items() if k != "entries"}
    assert current["entries"][:-1] == old["entries"]
    entry = json.loads((HERE / "publication-entry-draft.json").read_bytes())
    appended = current["entries"][-1]
    for key in ("publication_id", "case_id", "variant_id", "version", "package", "evidence_index"):
        assert appended[key] == entry[key]
    assert appended["evidence"] == f"{HERE.name}/cli-scope-signoff-2026-10-07.md"
    assert (HERE.parent / appended["evidence"]).is_file()
    assert appended["publication_id"] == index["publication_id"]
    assert sum(item["publication_id"] == appended["publication_id"] for item in current["entries"]) == 1
    scope = appended["scope"]
    assert all(term in scope for term in ("4044", "121 timed", "360cells", "NO_GO", "New native runs0",
                                          "Historical per-child PID/session unavailable", "no statistical formula"))
    assert disk_blob != staged_blob and json.loads(disk_blob) == json.loads(staged_blob)
    assert set(staged) <= ({CATALOG} | {f"{PKG}/{item['path']}" for item in index["source"]} |
                           {f"{PKG}/{name}" for name in EXTRA} | {f"{PKG}/evidence-index.json"})

    outcome = {"schema": "b03-var01-independent-staged-audit/v0.1.2", "decision": "GO_STAGED",
               "staged_paths": len(staged), "source_git_disk_equal": 129,
               "extra_review_git_disk_equal": len(EXTRA), "accepted_local_git_pairs": 38,
               "raw_records": 30, "context_copies": 88, "prior_catalog_entries_preserved": 489,
               "catalog_disk_sha256": pin(disk_blob)["sha256"],
               "catalog_staged_git_sha256": pin(staged_blob)["sha256"],
               "catalog_disk_git_bytes_distinct": True, "index_sha256": INDEX_SHA}
    print(json.dumps(outcome, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
