"""Independent read-only staged Git and catalog audit for C02.var01."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path


CASE = Path(__file__).resolve().parents[1]
ROOT = CASE.parents[2]
INDEX_SHA = "8bff77d2f543e82138e4191e6b83843f27b0b7fa684d3f919dd3399aed0f9221"
CATALOG = "cases/simlox-air-support/publication-index-v1.json"
BEFORE = ROOT / "tmp/publication-index-before-c02-var01-v101-20261007.json"


def git(*args: str) -> bytes:
    result = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, check=False)
    assert result.returncode == 0, (args, result.stderr.decode(errors="replace")[:200])
    return result.stdout


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def repo_path(path: Path) -> str:
    return path.resolve().relative_to(ROOT).as_posix()


def main() -> None:
    index_bytes = (CASE / "evidence-index.json").read_bytes()
    assert sha(index_bytes) == INDEX_SHA
    index = json.loads(index_bytes)
    expected: dict[str, bytes] = {}
    for pin in index["source_files"]:
        path = (CASE / pin["path"]).resolve()
        raw = path.read_bytes()
        assert len(raw) == pin["bytes"] and sha(raw) == pin["sha256"]
        expected[repo_path(path)] = raw
    assert len(expected) == 77
    extras = [CASE / "evidence-index.json",
              CASE / "review/independent-content-audit.py",
              CASE / "review/independent-content-go-2026-10-07.md"]
    for path in extras:
        expected[repo_path(path)] = path.read_bytes()
    assert len(expected) == 80
    staged_names = {name.decode("utf-8") for name in git("diff", "--cached", "--name-only", "-z").split(b"\0") if name}
    assert staged_names == set(expected) | {CATALOG}, (sorted(staged_names - set(expected)),
                                                     sorted(set(expected) - staged_names))
    assert len(staged_names) == 81
    for path, local in expected.items():
        staged = git("show", ":" + path)
        assert staged == local, (path, len(staged), sha(staged), len(local), sha(local))
    staged_index = git("show", ":" + repo_path(CASE / "evidence-index.json"))
    assert sha(staged_index) == INDEX_SHA

    old = json.loads(BEFORE.read_bytes())
    local_catalog_bytes = (ROOT / CATALOG).read_bytes()
    staged_catalog_bytes = git("show", ":" + CATALOG)
    local_catalog = json.loads(local_catalog_bytes)
    staged_catalog = json.loads(staged_catalog_bytes)
    assert local_catalog == staged_catalog
    assert len(old["entries"]) == 487 and len(local_catalog["entries"]) == 488
    assert local_catalog["entries"][:487] == old["entries"]
    assert {k: v for k, v in local_catalog.items() if k != "entries"} == {k: v for k, v in old.items() if k != "entries"}
    entry = json.loads((CASE / "publication-entry-draft.json").read_bytes())
    assert local_catalog["entries"][-1] == entry
    assert sum(x["publication_id"] == entry["publication_id"] for x in local_catalog["entries"]) == 1
    assert all("/runs/" not in name and not name.startswith("src/") for name in staged_names)
    git("-c", "core.whitespace=blank-at-eol,blank-at-eof,space-before-tab,cr-at-eol",
        "diff", "--cached", "--check")
    print(json.dumps({"schema": "c02-var01-v101-independent-staged-audit/v1",
                      "decision": "PASS", "staged_paths": len(staged_names),
                      "indexed_source_git_and_disk": 77, "additional_package_git_and_disk": 3,
                      "previous_catalog_entries": 487, "new_catalog_entries": 488,
                      "catalog_local_sha256": sha(local_catalog_bytes),
                      "catalog_staged_git_sha256": sha(staged_catalog_bytes),
                      "index_sha256": INDEX_SHA}, sort_keys=True))


if __name__ == "__main__":
    main()
