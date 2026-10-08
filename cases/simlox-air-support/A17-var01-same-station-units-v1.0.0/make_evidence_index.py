"""Reconstruct the closed, byte-only index for the bounded A17.var01 run.

No mode invokes SIMLOX, an accepted-parent checker, or either behavior reader.
Full verification needs the mandatory controlled-host originals named below.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path

import source_gate


CASE = Path(__file__).resolve().parent
REPO = CASE.parents[2]
TMP = REPO / "tmp"
INDEX = CASE / "evidence-index.json"
INVENTORY = CASE / "source-inventory.json"
MANIFEST = CASE / "prelaunch-manifest.json"
ENTRY = CASE / "publication-entry.json"
CATALOG = REPO / "cases/simlox-air-support/publication-index-v1.json"
GO = CASE / "review/independent-postrun-go.json"
SCOPE = CASE / "review/independent-postrun-scope-signoff-v2.md"
ROOT_CUSTODY = TMP / "a17-var01-root-native-custody-v100-20261008/20261008T172753084781Z-55f294be/receipt.json"
DRAFT = TMP / "a17-var01-postrun-draft-v100-20261009-01"
FIRST_RAW = DRAFT / "raw-custody-candidate.json"
FIRST_PREFLIGHT = DRAFT / "preflight-custody-candidate.json"
PROOF_MANIFEST = DRAFT / "publication-proof-originals.json"
PUB_ID = "A17.var01.two_explicit_units_same_station.1.0.0"
INVENTORY_PIN = (9141, "986e93597d1854488174fbc5a7608fa087950ac93de8def8f0d1fd23945b0974")
MANIFEST_PIN = (64092, "2dd0d83be96bd371405b502cb106422a795cab34500d49a30b20d36fd7b411a7")
GO_PIN = (1795, "006e6cce0df04483bc6423707cb98a71aa6a23110d1e2c3918805c415461d70c")
SCOPE_PIN = (2696, "dbc57c49053a485abf13f5cf5ea175e9b4343f8c4239295a2965c44a4a823740")
ROOT_PIN = (19688, "eae7f788886f2a2f7a5e9f9855c41540867a75e4c97e579b9a5644f1de77afe0")
FIRST_RAW_PIN = (21640, "665de94b5d33c1d501b6d55507891041dfb6e05d62c42083f637d47fd182ae5c")
FIRST_PREFLIGHT_PIN = (7608, "75a4bcca1316aeee15e6a01970366edbedb46cfe8fd0da49d8f5066d75bc8d01")
SMALL = {
    "model-run.log": (1079, "91f24e7779bef8a931ad656ddb8fe4341298090fe6e2251a6770fb2a0b6aaa4c", "preserved-raw/raw-000.bytes"),
    "model.log": (4039, "5a759e7a69521945275cfb5af67f58e822364187ce66c9941a1fe7b4ca5c76f0", "preserved-raw/raw-001.bytes"),
}
RUNTIME = {"runs", "test-output", "transport-evidence", "__pycache__"}
FUTURE = {
    "README-publication.md", "REPRODUCTION-postrun.md", "results-summary.json",
    "publication-entry.json", "cli-scope-signoff-2026-10-08.md",
    "make_evidence_index.py", "review/preflight-ssh0-20261008T172206568Z.json",
    "review/independent-prelaunch-go.json", "review/independent-postrun-go.json",
    "review/independent-postrun-scope-signoff-v2.md",
    "preserved-raw/custody.json", "preserved-preflight/custody.json",
    "preserved-postrun/custody.json",
}
PROOF_ROLES = {
    *(f"{stage}:{stream}" for stage in (
        "base_custody_candidate", "small_raw_candidate", "small_raw_promotion",
        "context_candidate", "context_promotion") for stream in ("receipt", "stdout", "stderr")),
    "method:build_custody", "method:small_raw_promoter", "method:context_copier",
    "method:root_publication_capture",
}


def pin(data: bytes) -> dict:
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def sealed(path: Path, expected: tuple[int, str] | None = None,
           require_readonly: bool = True) -> dict:
    assert path.is_file() and not path.is_symlink() and not path.is_junction(), str(path)
    if require_readonly:
        assert path.stat().st_file_attributes & 1, f"writable original: {path}"
    actual = pin(path.read_bytes())
    if expected is not None:
        assert actual == {"bytes": expected[0], "sha256": expected[1]}, str(path)
    return actual


def pairs_unique(items: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in items:
        assert key not in result, f"duplicate JSON key {key}"
        result[key] = value
    return result


def read(path: Path, expected: tuple[int, str] | None = None,
         require_readonly: bool = True) -> dict:
    sealed(path, expected, require_readonly)
    result = json.loads(path.read_bytes(), object_pairs_hook=pairs_unique,
                        parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    assert type(result) is dict, str(path)
    return result


def encode(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def integer(value: object, expected: int) -> None:
    assert type(value) is int and value == expected


def frozen_sources() -> tuple[dict, dict]:
    inventory = read(INVENTORY, INVENTORY_PIN)
    manifest = read(MANIFEST, MANIFEST_PIN)
    assert inventory["schema"] == "a17-var01-source-inventory/v1"
    assert manifest["schema"] == "a17-var01-prelaunch-manifest/v1"
    integer(inventory["source_count"], 53)
    integer(manifest["source_count"], 173)
    assert len(inventory["source_files"]) == 53 and len(manifest["source_files"]) == 173
    names = set()
    for row in inventory["source_files"]:
        assert set(row) == {"path", "bytes", "sha256"}
        rel = row["path"]
        assert type(rel) is str and rel not in names and not Path(rel).is_absolute() and ".." not in Path(rel).parts
        names.add(rel)
        assert sealed(CASE / rel) == {"bytes": row["bytes"], "sha256": row["sha256"]}
    keys = set()
    aliases = {}
    for row in manifest["source_files"]:
        assert set(row) == {"key", "path", "bytes", "sha256"}
        key = row["key"]
        assert type(key) is str and key.casefold() not in keys
        keys.add(key.casefold())
        path = Path(row["path"])
        assert path.is_absolute()
        identity = str(path.resolve(strict=True)).casefold()
        expected = (row["bytes"], row["sha256"])
        assert identity not in aliases or aliases[identity] == expected
        aliases[identity] = expected
        assert sealed(path, require_readonly=key.startswith("owned:")) == {
            "bytes": expected[0], "sha256": expected[1]}
    assert len(keys) == 173
    return inventory, manifest


def raw_custody() -> dict:
    first = read(FIRST_RAW, FIRST_RAW_PIN)
    amended = read(CASE / "preserved-raw/custody.json")
    preflight_first = read(FIRST_PREFLIGHT, FIRST_PREFLIGHT_PIN)
    preflight = read(CASE / "preserved-preflight/custody.json")
    assert first["schema"] == "a17-var01-postrun-raw-custody/v1"
    assert amended["schema"] == "a17-var01-postrun-raw-custody-with-small-copies/v1"
    assert preflight == preflight_first
    assert preflight["schema"] == "a17-var01-postrun-preflight-custody/v1"
    integer(amended["mandatory_original_count"], 39)
    integer(amended["recovered_run_copy_count"], 25)
    integer(amended["small_owned_raw_copy_count"], 2)
    integer(preflight["mandatory_original_count"], 15)
    assert len(amended["records"]) == 39 and len(preflight["records"]) == 15
    assert amended["original_raw_candidate"] == {"path": str(FIRST_RAW), **pin(FIRST_RAW.read_bytes())}
    base = {k: v for k, v in first.items() if k != "records"}
    derived = {k: v for k, v in amended.items() if k not in ("records", "small_owned_raw_copy_count", "original_raw_candidate")}
    base["schema"] = "a17-var01-postrun-raw-custody-with-small-copies/v1"
    assert base == derived
    custody = read(ROOT_CUSTODY, ROOT_PIN)
    assert len(custody["originals"]) == 39 and len(custody["recovered"]) == 25
    assert len({r["original_path"] for r in amended["records"]}) == 39
    assert len({r["original_path"] for r in preflight["records"]}) == 15
    small_seen = set()
    roles = {"native_run_original": 0, "native_pure_original": 0, "native_transport_original": 0}
    for initial, row in zip(first["records"], amended["records"], strict=True):
        name = Path(row["original_path"]).name
        if name in SMALL and row["role"] == "native_run_original":
            size, digest, rel = SMALL[name]
            assert row == {**initial, "owned_copy": rel}
            assert (row["bytes"], row["sha256"]) == (size, digest)
            assert sealed(CASE / rel) == {"bytes": size, "sha256": digest}
            small_seen.add(name)
        else:
            assert row == initial
        path = Path(row["original_path"])
        assert path.is_absolute() and str(path) in custody["originals"]
        assert sealed(path) == {"bytes": row["bytes"], "sha256": row["sha256"]}
        attributes = custody["originals"][str(path)]
        assert path.stat().st_mode == attributes["mode"]
        assert path.stat().st_file_attributes == attributes["attributes"]
        assert row["role"] in roles
        roles[row["role"]] += 1
        if row.get("recovered_copy") is not None:
            assert row["role"] == "native_run_original"
            assert sealed(Path(row["recovered_copy"])) == {"bytes": row["bytes"], "sha256": row["sha256"]}
    assert small_seen == set(SMALL)
    assert roles == {"native_run_original": 25, "native_pure_original": 11, "native_transport_original": 3}
    for row in preflight["records"]:
        assert row["role"] == "preflight_original"
        assert sealed(Path(row["original_path"])) == {"bytes": row["bytes"], "sha256": row["sha256"]}
    assert preflight["transport_self_captured"] is True and preflight["outer_transport_capture_exists"] is False
    for key in ("review_receipt", "pure_receipt", "transport_receipt"):
        item = preflight[key]
        assert sealed(Path(item["path"])) == {"bytes": item["bytes"], "sha256": item["sha256"]}
    return {"mandatory_native_original_count": 39, "mandatory_preflight_original_count": 15,
            "recovered_copy_count": 25, "small_owned_raw_copy_count": 2,
            "raw_custody_sha256": pin((CASE / "preserved-raw/custody.json").read_bytes())["sha256"],
            "preflight_custody_sha256": pin((CASE / "preserved-preflight/custody.json").read_bytes())["sha256"]}


def context_custody() -> dict:
    doc = read(CASE / "preserved-postrun/custody.json")
    assert doc["schema"] == "a17-var01-postrun-context-custody/v1"
    count = doc["original_count"]
    assert type(count) is int and count == doc["owned_copy_count"] == len(doc["records"])
    assert count == 77
    originals = set()
    for index, row in enumerate(doc["records"]):
        assert set(row) == {"original_path", "owned_copy", "bytes", "sha256", "original_if_present_must_match"}
        assert row["owned_copy"] == f"preserved-postrun/postrun-{index:03d}.bytes"
        assert row["original_if_present_must_match"] is True
        original = Path(row["original_path"])
        assert original.is_absolute() and original not in originals
        assert original.is_relative_to(TMP)
        originals.add(original)
        expected = {"bytes": row["bytes"], "sha256": row["sha256"]}
        assert sealed(CASE / row["owned_copy"]) == expected
        if original.exists():
            assert sealed(original) == expected
    return {"original_count": count, "owned_copy_count": count,
            "custody_sha256": pin((CASE / "preserved-postrun/custody.json").read_bytes())["sha256"]}


def publication_proofs() -> dict:
    doc = read(PROOF_MANIFEST)
    assert doc["schema"] == "a17-var01-publication-proof-originals/v1"
    rows = doc["records"]
    assert type(rows) is list and len(rows) == 19
    assert {row["role"] for row in rows} == PROOF_ROLES
    assert len({row["role"] for row in rows}) == 19
    by_role = {row["role"]: row for row in rows}
    for row in rows:
        assert set(row) == {"role", "path", "bytes", "sha256"}
        path = Path(row["path"])
        assert path.is_absolute() and path.is_relative_to(TMP)
        assert sealed(path) == {"bytes": row["bytes"], "sha256": row["sha256"]}
    for group in ("base_custody_candidate", "small_raw_candidate", "small_raw_promotion",
                  "context_candidate", "context_promotion"):
        triple = {row["role"].split(":", 1)[1]: row for row in rows if row["role"].startswith(group + ":")}
        receipt = read(Path(triple["receipt"]["path"]))
        integer(receipt["actual_exit"], 0)
        assert receipt["native_dispatch"] is False
        assert receipt["method_before"] == receipt["method_after"]
        method_role = {"base_custody_candidate": "method:build_custody",
                       "small_raw_candidate": "method:small_raw_promoter",
                       "small_raw_promotion": "method:small_raw_promoter",
                       "context_candidate": "method:context_copier",
                       "context_promotion": "method:context_copier"}[group]
        assert receipt["method_before"] == {
            "root_capture": {key: by_role["method:root_publication_capture"][key]
                             for key in ("bytes", "sha256")},
            "publication_method": {key: by_role[method_role][key] for key in ("bytes", "sha256")}}
        assert receipt["argv"][4] == by_role[method_role]["path"]
        for name in ("stdout", "stderr"):
            item = triple[name]
            assert Path(item["path"]).name == name + ".bin"
            assert receipt["streams"][name + ".bin"] == {"bytes": item["bytes"], "sha256": item["sha256"]}
        assert triple["stderr"]["bytes"] == 0
    return {"schema": doc["schema"], "manifest": {"path": str(PROOF_MANIFEST), **pin(PROOF_MANIFEST.read_bytes())},
            "mandatory_original_count": 19, "records": rows}


def case_source_rows(inventory: dict, context: dict) -> list[dict]:
    expected = {row["path"] for row in inventory["source_files"]}
    assert len(expected) == 53
    expected |= {"source-inventory.json", "prelaunch-manifest.json"}
    expected |= FUTURE
    expected |= {v[2] for v in SMALL.values()}
    expected |= {row["owned_copy"] for row in context["records"]}
    observed = set()
    for root, dirs, files in os.walk(CASE, topdown=True, followlinks=False):
        root_path = Path(root)
        if root_path == CASE:
            for name in dirs:
                item = root_path / name
                assert not item.is_symlink() and not item.is_junction(), str(item)
            dirs[:] = [name for name in dirs if name not in RUNTIME]
        for name in dirs:
            item = root_path / name
            assert not item.is_symlink() and not item.is_junction(), str(item)
        for name in files:
            path = root_path / name
            rel = path.relative_to(CASE).as_posix()
            assert not path.is_symlink() and not path.is_junction(), rel
            if rel != INDEX.name:
                observed.add(rel)
    assert len(observed) == len({p.casefold() for p in observed})
    assert observed == expected, {"missing": sorted(expected - observed), "unexpected": sorted(observed - expected)}
    rows = []
    for rel in sorted(expected):
        item = CASE / rel
        rows.append({"path": rel, **sealed(item)})
    return rows


def build() -> dict:
    inventory, manifest = frozen_sources()
    gate = source_gate.verify()  # Read-only Git ls-tree/cat-file and local source audit.
    assert gate["passed"] is True and gate["accepted_disk_git_pairs"] == 41
    assert gate["mandatory_originals"] == 61 and gate["catalog_prefix_entries"] == 501
    go = read(GO, GO_PIN)
    assert go["decision"] == "GO_BOUNDED_POSTRUN"
    sealed(SCOPE, SCOPE_PIN)
    entry = read(ENTRY)
    assert entry["publication_id"] == PUB_ID
    integer(entry["new_native_runs"], 1)
    integer(entry["accepted_parent_runs_repeated"], 0)
    assert entry["signoff"].endswith("review/independent-postrun-scope-signoff-v2.md")
    catalog = read(CATALOG, require_readonly=False)
    matches = [row for row in catalog["entries"] if row.get("publication_id") == PUB_ID]
    assert (len(catalog["entries"]) == 501 and not matches) or (
        len(catalog["entries"]) >= 502 and len(matches) == 1 and
        source_gate.typed_equal(catalog["entries"][501], entry))
    raw = raw_custody()
    context = read(CASE / "preserved-postrun/custody.json")
    context_summary = context_custody()
    proofs = publication_proofs()
    sources = case_source_rows(inventory, context)
    assert len(sources) == 147
    return {"schema": "a17-var01-bounded-evidence-index/v1", "publication_id": PUB_ID,
            "bounded_decision": go["decision"], "new_native_runs": 1,
            "accepted_parent_runs_repeated": 0, "frozen_prelaunch_owned_sources": 53,
            "frozen_prelaunch_roles": 173, "mandatory_prelaunch_originals": 61,
            "catalog_historical_prefix_entries": 501,
            "source_count": len(sources), "source_files": sources,
            "raw_and_preflight": raw, "postrun_context": context_summary,
            "mandatory_publication_proof_originals": proofs,
            "observed_primary": {"full_log_lines": 60, "timed_log_lines": 52,
                                 "authored_cells": 203, "exported_cells": 387,
                                 "report_typed_cells": 4044, "native_commands": 4,
                                 "pure_checker_stages": 2}}


def main() -> None:
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--candidate", type=Path)
    modes.add_argument("--write", action="store_true")
    modes.add_argument("--dry", action="store_true")
    args = parser.parse_args()
    body = encode(build())
    if args.candidate is not None:
        target = args.candidate
        assert target.is_absolute() and target.parent == DRAFT and not target.is_relative_to(CASE)
        with target.open("xb") as handle:
            handle.write(body)
        target.chmod(target.stat().st_mode & ~0o222)
    elif args.write:
        with INDEX.open("xb") as handle:
            handle.write(body)
        INDEX.chmod(INDEX.stat().st_mode & ~0o222)
    elif not args.dry:
        assert INDEX.read_bytes() == body, "canonical index differs from byte reconstruction"
    print(json.dumps({"schema": "a17-var01-evidence-index-check/v1", "bytes": len(body),
                      "sha256": pin(body)["sha256"], "source_count": json.loads(body)["source_count"],
                      "wrote_canonical": args.write}, sort_keys=True))


if __name__ == "__main__":
    main()
