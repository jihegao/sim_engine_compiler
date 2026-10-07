"""Independent read-only audit of the exact staged C09.var02 publication."""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
REPO = Path(__file__).resolve().parents[4]
INDEX_SHA = "546a179249ca03f98151c2274eb82be73d6890bdbf1a18bde786ce62d59becda"
CONTENT_AUDIT_SHA = "896a44841b34738bd1da4f4419db8862c84128773b3c264f063380bbf8e38e1b"
CONTENT_MEMO_SHA = "265dae06f4cf77b84bf39779ad79a88964abb362a4dcd420ff0a7aae4f78a11c"
BASE = "d1d9a4dcbcfe146a0de41e01c3089dae235bb7ef"
CATALOG_DISK = {"bytes": 484891, "sha256": "1c092a95bf369e0985a1cea8e037067d7664685a21a6f7c98f3de84cc32af7ae"}
CATALOG_STAGED = {"bytes": 484324, "sha256": "e7abaebe623f0add9ba9430fd917aa3e15641bcd6432309ff557b2b5e966e20f"}


def sha(data: bytes) -> dict:
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def run(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=REPO, check=check, stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE)


def rel(path: Path) -> str:
    return path.resolve().relative_to(REPO).as_posix()


def staged(path: str) -> bytes:
    return run("git", "show", f":{path}").stdout


def load(data: bytes) -> dict:
    return json.loads(data.decode("utf-8-sig"))


def audit() -> dict:
    index_path = PKG / "evidence-index.json"
    index_bytes = index_path.read_bytes()
    assert sha(index_bytes)["sha256"] == INDEX_SHA
    index = load(index_bytes)
    source = index["source_files"]
    assert index["source_count"] == len(source) == 184
    staged_paths = set(filter(None, run("git", "diff", "--cached", "--name-only", "-z").stdout.decode().split("\0")))
    expected = {rel((PKG / item["path"]).resolve()) for item in source}
    extra = {rel(index_path),
             rel(PKG / "review/independent-content-audit.py"),
             rel(PKG / "review/independent-content-go-2026-10-07.md"),
             rel(PKG.parent / "publication-index-v1.json")}
    assert len(expected) == 184 and staged_paths == expected | extra and len(staged_paths) == 188
    for item in source:
        path = (PKG / item["path"]).resolve()
        expected_seal = {key: item[key] for key in ("bytes", "sha256")}
        assert sha(path.read_bytes()) == expected_seal, (path, "disk")
        assert sha(staged(rel(path))) == expected_seal, (path, "staged Git blob")
        assert "runs" not in path.parts
    assert sha(staged(rel(index_path))) == sha(index_bytes)
    for path, digest in ((PKG / "review/independent-content-audit.py", CONTENT_AUDIT_SHA),
                         (PKG / "review/independent-content-go-2026-10-07.md", CONTENT_MEMO_SHA)):
        assert sha(path.read_bytes())["sha256"] == digest
        assert sha(staged(rel(path))) == sha(path.read_bytes())
    # Compare parsed catalog values, retaining the exact old 486 entries and
    # every non-entry metadata field. Old disk/Git bytes differ; new stage
    # may have matching or different bytes depending on its serialization.
    catalog_path = PKG.parent / "publication-index-v1.json"
    current_disk = catalog_path.read_bytes()
    current_git = staged(rel(catalog_path))
    assert sha(current_disk) == CATALOG_DISK and sha(current_git) == CATALOG_STAGED
    assert load(current_disk) == load(current_git)
    catalog = load(current_disk)
    old_git = run("git", "show", f"{BASE}:{rel(catalog_path)}").stdout
    old_local = (PKG.parent / "C09-var02-lender-shortage-v1.0.7/preserved-root-context/publication-index-at-base.json").read_bytes()
    old = load(old_local)
    assert old_local != old_git and load(old_git) == old
    assert len(old["entries"]) == 486 and len(catalog["entries"]) == 487
    assert catalog["entries"][:486] == old["entries"]
    assert {key: value for key, value in catalog.items() if key != "entries"} == {
        key: value for key, value in old.items() if key != "entries"}
    draft = load((PKG / "publication-entry-draft.json").read_bytes())
    assert catalog["entries"][-1] == draft
    ids = [entry["publication_id"] for entry in catalog["entries"]]
    assert len(ids) == len(set(ids))
    assert draft["positive_pair_accepted"] is False and draft["v107_child_decision"] == "NO_GO_RUN"
    assert draft["new_native_runs"] == 0
    # Reuse the separate reviewer content audit, which independently rehashes
    # 156 local raw seals and 77 base-Git/local source identities.
    content = load(run(sys.executable, "-B", str(PKG / "review/independent-content-audit.py")).stdout)
    assert content["source_pins"] == 184 and content["raw_pins"] == 156
    assert content["accepted_disk_git_refs"] == 77 and content["excluded_v106_raw_seals"] == 8
    check = run("git", "-c", "core.whitespace=cr-at-eol", "diff", "--cached", "--check", check=False)
    assert check.returncode == 2
    lines = check.stdout.decode("utf-8", errors="replace").splitlines()
    warnings = [line for line in lines if ": trailing whitespace." in line or ": new blank line at EOF." in line]
    assert len(warnings) == 12, warnings
    allowed = {
        "C09-var02-lender-shortage-return-v0.1.0/physical_ledger.py",
        "C09-var02-lender-shortage-return-v0.1.0/preserved-root-context/c09-var02-v106-native-transport-20261007T064439238Z.txt",
        "C09-var02-lender-shortage-return-v0.1.0/preserved-root-context/c09-var02-v107-native-transport-20261007T073525680Z.txt",
        "C09-var02-lender-shortage-v1.0.5/physical_ledger.py",
        "C09-var02-lender-shortage-v1.0.6/physical_ledger.py",
        "C09-var02-lender-shortage-v1.0.7/physical_ledger.py",
        "C09-var02-lender-shortage-v1.0.7/preserved-root-context/c09-var02-v106-native-transport-20261007T064439238Z.txt",
    }
    assert all(any(name in warning for name in allowed) for warning in warnings)
    assert all("trailing whitespace." in warning or "new blank line at EOF." in warning for warning in warnings)
    assert all(line in warnings or line.startswith("+") for line in lines), lines
    return {"decision": "GO_STAGED_BYTE_AUDIT", "staged_paths": 188,
            "indexed_source_disk_and_git_pins": 184,
            "extra_index_content_review_and_catalog_paths": 4,
            "raw_pins": 156, "accepted_local_git_refs": 77,
            "catalog_prior_entries_preserved": 486, "catalog_new_entries": 1,
            "catalog_new_disk_git_bytes_equal": current_disk == current_git,
            "catalog_old_disk_git_bytes_distinct": old_local != old_git,
            "byte_preservation_whitespace_notices": len(warnings),
            "native_raw_or_product_paths_staged": 0,
            "new_native_runs": 0, "v107_child_decision": "NO_GO_RUN"}


if __name__ == "__main__":
    assert sys.argv[1:] == [], "usage: independent-staged-audit.py"
    print(json.dumps(audit(), sort_keys=True, indent=2))
