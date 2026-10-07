"""Read-only byte audit for the corrected E08.var04 publication candidate."""

import hashlib
import json
import subprocess
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1]
REPO = next(p for p in PACKAGE.parents if (p / ".git").exists())
INDEX = PACKAGE / "evidence-index-v2.json"
OLD_INDEX = PACKAGE / "evidence-index.json"
EXPECTED_INDEX = "4e429a35cae031c0a79c6ce3ecbeb4c1cc963512d10e6d84f5839102e78a4fab"
EXPECTED_OLD = "d54410100e50d0ed0b1ca866fea79a4e2b9b91f0510a3542d32e7b305b095bb3"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def check(path, pin):
    raw = path.read_bytes()
    assert len(raw) == pin["bytes"] and digest(raw) == pin["sha256"], str(path)


def main():
    assert digest(INDEX.read_bytes()) == EXPECTED_INDEX
    assert digest(OLD_INDEX.read_bytes()) == EXPECTED_OLD
    index = json.loads(INDEX.read_bytes())
    old = json.loads(OLD_INDEX.read_bytes())
    assert index["schema"] == "e08-var04-current-future-peer-evidence-index/v2"
    assert index["source_base_commit"] == "66eefcedd8108249ebd73eebdc0a205e15ae84e2"
    assert index["source"] == index["source_files"]
    assert len(index["source_files"]) == index["source_count"] == 137
    for pin in index["source_files"]:
        assert "preserved-excluded-source/" not in pin["path"]
        check((PACKAGE / pin["path"]).resolve(), pin)
    assert len(old["source_files"]) == 118
    for pin in old["source_files"]:
        check((PACKAGE / pin["path"]).resolve(), pin)
    refs = index["accepted_source_refs"]
    assert len(refs) == 49
    for ref in refs:
        local = (PACKAGE / ref["path"]).resolve()
        check(local, ref["local_disk"])
        git_path = local.relative_to(REPO).as_posix()
        published = subprocess.run(
            ["git", "show", index["source_base_commit"] + ":" + git_path],
            cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
        ).stdout
        pin = ref["published_git_at_base"]
        assert len(published) == pin["bytes"] and digest(published) == pin["sha256"], git_path
    assert len(index["raw_files"]) == 220
    assert sum(r["status"] == "accepted" for r in index["raw_files"]) == 110
    for pin in index["raw_files"]:
        check(Path(pin["original_path"]), pin)
    assert len(index["context_copies"]) == 11
    for pin in index["context_copies"]:
        check(PACKAGE / pin["copy_path"], pin)
        original = Path(pin["original_path"])
        if original.exists():
            check(original, pin)
    copies = index["excluded_unpublished_source_copies"]
    assert len(copies) == 22
    assert json.loads((PACKAGE / "excluded-source-custody-map-v2.json").read_bytes()) == copies
    for pin in copies:
        check(Path(pin["original_path"]), pin)
        check(PACKAGE / pin["rejected_v1_copy_path"], pin)
        check(PACKAGE / pin["copy_path"], pin)
    safe = PACKAGE / "preserved-excluded-source-v2"
    assert not [p for p in safe.rglob("*") if p.is_file() and p.name in (".gitattributes", ".gitignore")]
    assert len([p for p in safe.rglob("*") if p.is_file()]) == 22
    entry = json.loads((PACKAGE / "publication-entry-draft-v2.json").read_bytes())
    assert entry["new_native_runs"] == 0
    assert entry["evidence_index"] == PACKAGE.relative_to(REPO / "cases" / "simlox-air-support").as_posix() + "/evidence-index-v2.json"
    for key in ("evidence", "readme", "reproduction_guide", "contract", "signoff"):
        assert (REPO / "cases" / "simlox-air-support" / entry[key]).is_file(), key
    print(json.dumps({"decision": "GO_CONTENT_BYTES", "index_sha256": EXPECTED_INDEX,
                      "source": 137, "old_source": 118, "published_refs": 49,
                      "raw": 220, "context": 11, "safe_copies": 22}, sort_keys=True))


if __name__ == "__main__":
    main()
