"""Read-only exact Git index audit for E08.var04 v2 publication."""

import hashlib
import json
import subprocess
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
REPO = next(p for p in PACKAGE.parents if (p / ".git").exists())
INDEX = PACKAGE / "evidence-index-v2.json"
CATALOG = "cases/simlox-air-support/publication-index-v1.json"
CONTENT = (
    "review/independent-content-audit-v2.py",
    "review/independent-content-go-v2-2026-10-07.md",
)


def git(*args):
    return subprocess.run(["git", *args], cwd=REPO, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE, check=True).stdout


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    idx = json.loads(INDEX.read_bytes())
    base = PACKAGE.relative_to(REPO).as_posix()
    expected = {CATALOG, base + "/evidence-index-v2.json"}
    expected.update(base + "/" + x for x in CONTENT)
    for pin in idx["source_files"]:
        path = (PACKAGE / pin["path"]).resolve()
        relative = path.relative_to(REPO).as_posix()
        assert "preserved-excluded-source/" not in relative
        raw = path.read_bytes()
        blob = git("show", ":" + relative)
        assert len(raw) == pin["bytes"] and digest(raw) == pin["sha256"], relative
        assert blob == raw, relative
        expected.add(relative)
    assert len(idx["source_files"]) == 137
    for extra in ("evidence-index-v2.json", *CONTENT):
        path = PACKAGE / extra
        relative = path.relative_to(REPO).as_posix()
        assert git("show", ":" + relative) == path.read_bytes(), relative
    paths = set(git("diff", "--cached", "--name-only", "-z").decode().rstrip("\0").split("\0"))
    assert paths == expected, {"missing": sorted(expected - paths), "extra": sorted(paths - expected)}
    assert len(paths) == 141
    old = json.loads(git("show", "HEAD:" + CATALOG))
    staged_bytes = git("show", ":" + CATALOG)
    staged = json.loads(staged_bytes)
    old_meta = {k: v for k, v in old.items() if k != "entries"}
    new_meta = {k: v for k, v in staged.items() if k != "entries"}
    assert old_meta == new_meta
    assert len(old["entries"]) == 488 and len(staged["entries"]) == 489
    assert staged["entries"][:-1] == old["entries"]
    entry = staged["entries"][-1]
    draft = json.loads((PACKAGE / "publication-entry-draft-v2.json").read_bytes())
    assert entry["package"] == draft["package"]
    assert entry["case_id"] == draft["case_id"]
    assert entry["variant_id"] == draft["variant_id"]
    assert entry["version"] == draft["version"]
    assert entry["evidence_index"] == PACKAGE.name + "/evidence-index-v2.json"
    assert entry["evidence"] == PACKAGE.name + "/cli-scope-signoff-v2-2026-10-07.md"
    assert "48684" in entry["scope"] and "New native runs0" in entry["scope"]
    assert "NO_GO_PUBLICATION_ARCHIVE_ATTRIBUTES" in entry["scope"]
    assert staged_bytes != (REPO / CATALOG).read_bytes(), "catalog disk/Git identity unexpectedly conflated"
    assert not any("preserved-excluded-source/" in p for p in paths)
    print(json.dumps({"decision": "GO_STAGED_BYTES", "paths": len(paths),
                      "new_source_blobs": 137, "catalog_before": 488,
                      "catalog_after": 489, "catalog_staged_sha256": digest(staged_bytes),
                      "catalog_disk_sha256": digest((REPO / CATALOG).read_bytes())}, sort_keys=True))


if __name__ == "__main__":
    main()
