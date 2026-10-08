"""Read-only custody gate for the accepted I04.var01 evidence reused by I04.var06.

No SIMLOX invocation or Git command occurs here. The inherited 76 Git blobs were
checked by the separately captured root selection; this gate rechecks that
signed selection's byte-bound map and every current disk counterpart.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import stat
from pathlib import Path

CASE = Path(__file__).resolve().parents[1]
REPO = CASE.parents[2]
PARENT = REPO / "cases/simlox-air-support/I04-var01-system-between-v1.0.0"
RECOVERY = REPO / "tmp/i04-var06-return-complete-classification-v100-20261008-01"

PINS = {
    "contract.json": (10668, "87a22902a86bde7d9d668d816830bd5b4b87ee6b6c4d6f289bf94190f83b90a2"),
    "contract.md": (5589, "a68a8c21bb83ec4b5e2a2ea2a7fb5faef0819ae6a14329197e2e8726653e8036"),
    "preserved-context/root-selection-receipt.json.bytes": (13588, "2f97e7766570da48201fa4837bff67949731b280c36c9f832860f6c5f652b889"),
    "source-maps/dependency-pairs.json": (32666, "202a4c265fcc04206247299d61b75f77f6b70b2477521f2c84843fd9c1f4c0d7"),
}
PARENT_INDEX = (7440, "7cc499df680969e65d178d9c1db90c32c44e80d784f3b6d2f75d50532b7d102b")
PARENT_VERDICT = (1340, "944bcac5d31ab378eb56dd4ae1983451cdd82b3e4463d4509577aa91e7531b32")
PARENT_SIGNOFF = (2243, "fa6de03b946b519e626efb5a85498db2049b2d92821feb7346fd4300b5982768")
MANUAL = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")
MANUAL_SHA = "39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3"
DICTIONARY = Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt")
DICTIONARY_SHA = "11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0"
RECOVERY_MANIFEST = (18781, "95ca366f43382a6370105231dabf58e0d9622b831611c47929a9582c79468789")
SELECTION_CAPTURE = REPO / "tmp/i04-var06-root-selection-20261008/20261008T150201856194Z-f57fceea"
CATALOG_LOCAL = (541490, "76e1f2d1a46e2436380131bffa94f49d47fddb72361af8b83d28dc365ac4e668")
CATALOG_GIT = (536774, "e2f999a4b0f612f33798f9bb70cb7b94c387f89b1d5531301b3919d49ce5ca98")


def pin(data: bytes) -> dict[str, object]:
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def exact(path: Path, expected: dict | tuple[int, str]) -> bytes:
    data = path.read_bytes()
    if isinstance(expected, tuple):
        required = {"bytes": expected[0], "sha256": expected[1]}
    else:
        required = {"bytes": expected["bytes"], "sha256": expected["sha256"]}
    assert pin(data) == required, f"byte pin mismatch: {path}"
    return data


def load(data: bytes) -> object:
    def unique(pairs: list[tuple[str, object]]) -> dict:
        out = {}
        for key, value in pairs:
            assert key not in out, f"duplicate key: {key}"
            out[key] = value
        return out

    return json.loads(data, object_pairs_hook=unique,
                      parse_constant=lambda s: (_ for _ in ()).throw(ValueError(s)))


def typed_equal(left: object, right: object) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(typed_equal(left[k], right[k]) for k in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(typed_equal(a, b) for a, b in zip(left, right))
    return left == right


def within_repo(relative: str) -> Path:
    assert isinstance(relative, str) and relative and "\\" not in relative
    p = Path(relative)
    assert not p.is_absolute() and ".." not in p.parts
    resolved = (REPO / p).resolve(strict=True)
    assert resolved.is_relative_to(REPO.resolve(strict=True))
    return resolved


def verify(recovery: Path = RECOVERY) -> dict[str, int | str]:
    assert recovery == RECOVERY and recovery.is_dir()
    assert not recovery.is_symlink() and not recovery.is_junction()
    for rel, (size, digest) in PINS.items():
        data = (CASE / rel).read_bytes()
        assert len(data) == size and (digest is None or pin(data)["sha256"] == digest), rel
    # The map is an exact owned copy of the root selection's 76-row file.
    selection = load((CASE / "preserved-context/root-selection-receipt.json.bytes").read_bytes())
    pairs = load((CASE / "source-maps/dependency-pairs.json").read_bytes())
    assert selection["decision"] == "ELIGIBLE_FOR_PROSPECTIVE_CONTRACT_ONLY"
    assert selection["base"] == "fdaba58276b8efc87c4abc72d0a1d56247dc9538"
    assert selection["accepted_parent_dependency_pairs"] == 76 and len(pairs) == 76
    assert selection["originals_readonly_count"] == 0
    # No author Git call: the captured pair map records the root's fixed-base
    # blob checks. Fresh disk files are rehashed here.
    seen_paths: set[str] = set()
    for row in pairs:
        assert set(row) == {"path", "oid", "disk", "git", "byte_equal"}
        assert row["path"] not in seen_paths and len(row["oid"]) == 40
        seen_paths.add(row["path"])
        disk = exact(within_repo(row["path"]), row["disk"])
        assert row["byte_equal"] is (row["disk"] == row["git"])
        assert isinstance(disk, bytes)
    index = load(exact(PARENT / "evidence-index.json", PARENT_INDEX))
    assert selection["parent_index"] == pin((PARENT / "evidence-index.json").read_bytes())
    assert set(index["source"]) and len(index["source"]) == 15
    assert selection["parent_source_files"] == 15
    for name, row in index["source"].items():
        exact(within_repo(f"cases/simlox-air-support/I04-var01-system-between-v1.0.0/{name}"), row)
    assert pin(MANUAL.read_bytes()) == {"bytes": 18124110, "sha256": MANUAL_SHA}
    assert pin(DICTIONARY.read_bytes()) == {"bytes": 78577, "sha256": DICTIONARY_SHA}
    verdict = load(exact(PARENT / "review/independent-verdict.json", PARENT_VERDICT))
    assert verdict["verdict"] == "GO_BOUNDED" and verdict["checks"] == verdict["passed"] == 439
    assert verdict["failed"] == []
    exact(PARENT / "cli-scope-signoff-2026-10-05.md", PARENT_SIGNOFF)

    local = exact(SELECTION_CAPTURE / "catalog-local-500.json.bytes", CATALOG_LOCAL)
    git = exact(SELECTION_CAPTURE / "catalog-git-500.json.bytes", CATALOG_GIT)
    assert local.replace(b"\r\n", b"\n") == git and local != git
    local_catalog = load(local)
    git_catalog = load(git)
    assert typed_equal(local_catalog, git_catalog)
    assert len(local_catalog["entries"]) == 500
    current = load((REPO / "cases/simlox-air-support/publication-index-v1.json").read_bytes())
    assert len(current["entries"]) >= 500
    assert current.keys() == local_catalog.keys()
    assert typed_equal({k: v for k, v in current.items() if k != "entries"},
                       {k: v for k, v in local_catalog.items() if k != "entries"})
    assert typed_equal(current["entries"][:500], local_catalog["entries"])
    assert not any(row.get("variant_id") == "I04.var06" for row in local_catalog["entries"])

    original_by_name = {}
    run = Path(index["run"]["local_directory"])
    assert run == PARENT / "runs/i04-var01-system-between-v100-ssh-20261005-01"
    raw = {**index["run"]["raw"], "invocation.json": index["run"]["invocation"],
           "closure.json": index["run"]["closure"]}
    assert len(raw) == len(selection["originals"]) == 24
    for row in selection["originals"]:
        path = Path(row["path"])
        assert path.parent == run and path.name in raw and path.name not in original_by_name
        assert row["read_only_observed"] is False
        assert {"bytes": row["bytes"], "sha256": row["sha256"]} == {
            "bytes": raw[path.name]["bytes"], "sha256": raw[path.name]["sha256"]}
        exact(path, row)
        original_by_name[path.name] = row
    assert set(original_by_name) == set(raw)

    manifest = load(exact(recovery / "recovery-manifest.json", RECOVERY_MANIFEST))
    assert manifest["copies_count"] == 24 and manifest["native_calls"] == 0
    assert manifest["accepted_checker_calls"] == 0 and manifest["semantic_acceptance"] is False
    assert len(manifest["copies"]) == 24
    seen_copy_names: set[str] = set()
    for row in manifest["copies"]:
        assert set(row) == {"name", "original_path", "copy_path", "bytes", "sha256",
                            "original_mode_before", "original_attributes_before",
                            "original_mode_after", "original_attributes_after", "copy_readonly"}
        name = row["name"]
        assert name in original_by_name and name not in seen_copy_names
        seen_copy_names.add(name)
        original = Path(row["original_path"])
        copy = Path(row["copy_path"])
        assert original == Path(original_by_name[name]["path"])
        assert copy == recovery / "raw" / name
        assert copy.resolve(strict=True) == copy and not copy.is_symlink() and not copy.is_junction()
        assert row["original_mode_before"] == row["original_mode_after"]
        assert row["original_attributes_before"] == row["original_attributes_after"]
        s = original.stat()
        assert s.st_mode == row["original_mode_after"]
        assert s.st_file_attributes == row["original_attributes_after"]
        assert {"bytes": row["bytes"], "sha256": row["sha256"]} == {
            "bytes": original_by_name[name]["bytes"], "sha256": original_by_name[name]["sha256"]}
        exact(original, row)
        exact(copy, row)
        assert row["copy_readonly"] is True and not (copy.stat().st_mode & stat.S_IWRITE)
    assert seen_copy_names == set(raw)
    return {"parent_sources": 15, "dependency_disk_rows": 76, "inherited_git_pair_rows": 76,
            "mandatory_originals": 24, "read_only_copies": 24, "catalog_prefix": 500,
            "manual_sha256": MANUAL_SHA}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--recovery-dir", type=Path, default=RECOVERY)
    args = parser.parse_args()
    print(json.dumps({"schema": "i04-var06-author-source-gate/v100", "passed": True,
                      **verify(args.recovery_dir)}, sort_keys=True))
