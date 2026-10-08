"""Byte-only closed-index reconstruction for E02.var02 v1.0.4.

The reviewed custody, context, and proof pins below close the publishable bytes.
This method never writes the canonical index; root controls its promotion.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

CASE = Path(r"C:\Users\user\Documents\Codex\2026-09-29\simlox-c04-deadline\repo\cases\simlox-air-support\E02-var02-repair-return-after-deadline-v1.0.4")
REPO = CASE.parents[2]
TMP = REPO / "tmp"
INDEX = CASE / "evidence-index.json"
CATALOG = REPO / "cases/simlox-air-support/publication-index-v1.json"
INVENTORY = CASE / "source-inventory.json"
MANIFEST = CASE / "prelaunch-manifest.json"
SOURCE_GATE = CASE / "source_gate.py"
GO = CASE / "review/independent-postrun-go.json"
GO_SCOPE = CASE / "review/independent-postrun-scope-go-2026-10-09.md"
RAW_MAP = CASE / "preserved-raw/raw-originals.json"
PREFLIGHT_MAP = CASE / "preserved-preflight/custody.json"
SMALL_MAP = CASE / "preserved-raw/small-copies.json"
CONTEXT_MAP = CASE / "preserved-postrun/custody.json"
PROOF_MANIFEST = TMP / "e02-var02-v104-publication-proof-originals-20261009.json"
PUB_ID = "E02.var02.repair_return_after_deadline.1.0.4"
RUN_ID = "e02-var02-repair-deadline-v104-ssh-20261009-01"

INVENTORY_PIN = (6970, "8468cca1be0372212ce158dc1833271bdf884ce47ba89bd66cec23bec2bcbef9")
MANIFEST_PIN = (103633, "4f1ef0db0aa97709c2c8c1d4f246851321e23b83200412155f97849bc2afbc0f")
GO_PIN = (1666, "d1b8686bbf4050f90c7d43e159e7ca7d9f5dfab1d2ab25f12e7ef6d700236b81")
GO_SCOPE_PIN = (2155, "4efa1fb2fd602eb9202c637410c5f5840f29e76417200e6f99d94d92315e649d")
ROOT_NATIVE = TMP / "e02-var02-root-native-custody-v104-20261009/20261008T224605902635Z-85fd3482/receipt.json"
ROOT_NATIVE_PIN = (17065, "926766936689bfbf0d10d428f59cf9df583b724b6f93fe6e0297a1aba86399d6")
ROOT_PREFLIGHT = TMP / "e02-var02-root-preflight-seal-v104-20261009.json"
ROOT_PREFLIGHT_PIN = (5468, "d895b98b4d2b029b1bcbba1bf515533c9ae515a8cafc29a1c04742d3ec17d7b6")
FAILED_INDEX = TMP / "e02-var02-failed-index-construction-v103-20261009-01/receipt.json"
FAILED_INDEX_PIN = (2663, "ebf4f4531853ee9a189e8898f3f0a0f92671a6c89a67acc824c9500dbbbaf00e")
FAILED_SOURCE_PIN = {"bytes": 25052, "sha256": "8148074b6bdb8b4eff32918a21cad9b2fba170026159bf79f7cb16037ee982a7"}
SELECTION = CASE / "source-maps/root-selection-receipt.json"
SELECTION_PIN = (37595, "1207a61dc842fba2c0102c4ea03bbc142b7fd8f560ae3970df67bcc47e3a12f5")
ARCHIVE_LOCAL = CASE / "source-maps/catalog-local-503.json.bytes"
ARCHIVE_GIT = CASE / "source-maps/catalog-git-503.json.bytes"
ARCHIVE_LOCAL_PIN = (547545, "ff5945845d8014375c7f9db0eba62369b50308f3aab9dc3a6ffba0e6f93f102b")
ARCHIVE_GIT_PIN = (542763, "cfd70fd9d9b4054d3658962908bff6e435528e1f012dda84c2aae61325ff0aba")

# Exact separately reviewed publication custody identities.
RAW_MAP_PIN: tuple[int, str] | None = (22521, "c0f884fce6bbc9f2b9597d4c5256c6be1668351a0b9d30110e24309f8d94e06e")
PREFLIGHT_MAP_PIN: tuple[int, str] | None = (7203, "e0757098caeb4bc740bafe49f4ec7b94be2c3cde81cf3942fd3774b770f6faf1")
SMALL_MAP_PIN: tuple[int, str] | None = (1344, "5822346f23e059ac100ab4ef89e21f4c360a43ba9219c10b708a5a77c516f020")
CONTEXT_MAP_PIN: tuple[int, str] | None = (47733, "6fdbca6adef95ede367a0c4ccdd019b4b1cb7971ff5e46353b29a5810fc294e4")
PROOF_MANIFEST_PIN: tuple[int, str] | None = (54506, "0bc5b238358250d947a8c7c40b03221b85e8c3685d7a477271d72b82961f9401")
EXPECTED_CONTEXT_COPIES: int | None = 111
PROOF_ROLES: frozenset[str] | None = frozenset((
    "prior:fixed_root_proof_plan",
    "prior:capture:00:receipt",
    "prior:capture:00:stdout.bin",
    "prior:capture:00:stderr.bin",
    "prior:method:capture:00",
    "prior:capture:01:receipt",
    "prior:capture:01:stdout.bin",
    "prior:capture:01:stderr.bin",
    "prior:capture:02:receipt",
    "prior:capture:02:stdout.bin",
    "prior:capture:02:stderr.bin",
    "prior:capture:03:receipt",
    "prior:capture:03:stdout.bin",
    "prior:capture:03:stderr.bin",
    "prior:method:capture:03",
    "prior:capture:04:receipt",
    "prior:capture:04:stdout.bin",
    "prior:capture:04:stderr.bin",
    "prior:capture:05:receipt",
    "prior:capture:05:stdout.bin",
    "prior:capture:05:stderr.bin",
    "prior:capture:06:receipt",
    "prior:capture:06:stdout.bin",
    "prior:capture:06:stderr.bin",
    "prior:capture:07:receipt",
    "prior:capture:07:stdout.bin",
    "prior:capture:07:stderr.bin",
    "prior:method:capture:07",
    "prior:capture:08:receipt",
    "prior:capture:08:stdout.bin",
    "prior:capture:08:stderr.bin",
    "prior:method:capture:08",
    "prior:capture:09:receipt",
    "prior:capture:09:stdout.bin",
    "prior:capture:09:stderr.bin",
    "prior:method:capture:09",
    "prior:capture:10:receipt",
    "prior:capture:10:stdout.bin",
    "prior:capture:10:stderr.bin",
    "prior:capture:11:receipt",
    "prior:capture:11:stdout.bin",
    "prior:capture:11:stderr.bin",
    "prior:capture:12:receipt",
    "prior:capture:12:stdout.bin",
    "prior:capture:12:stderr.bin",
    "prior:capture:13:receipt",
    "prior:capture:13:stdout.bin",
    "prior:capture:13:stderr.bin",
    "prior:method:capture:13",
    "prior:capture:14:receipt",
    "prior:capture:14:stdout.bin",
    "prior:capture:14:stderr.bin",
    "prior:capture:15:receipt",
    "prior:capture:15:stdout.bin",
    "prior:capture:15:stderr.bin",
    "prior:method:capture:15",
    "prior:capture:16:receipt",
    "prior:capture:16:stdout.bin",
    "prior:capture:16:stderr.bin",
    "prior:capture:17:receipt",
    "prior:capture:17:stdout.bin",
    "prior:capture:17:stderr.bin",
    "prior:method:capture:17",
    "prior:capture:18:receipt",
    "prior:capture:18:stdout.bin",
    "prior:capture:18:stderr.bin",
    "prior:method:capture:18",
    "prior:capture:19:receipt",
    "prior:capture:19:stdout.bin",
    "prior:capture:19:stderr.bin",
    "prior:method:capture:19",
    "prior:capture:20:receipt",
    "prior:capture:20:stdout.bin",
    "prior:capture:20:stderr.bin",
    "prior:capture:21:receipt",
    "prior:capture:21:stdout.bin",
    "prior:capture:21:stderr.bin",
    "prior:capture:22:receipt",
    "prior:capture:22:stdout.bin",
    "prior:capture:22:stderr.bin",
    "prior:method:capture:22",
    "prior:formal_static:0:stdout",
    "prior:formal_static:0:stderr",
    "prior:formal_static:1:stdout",
    "prior:formal_static:1:stderr",
    "prior:formal_static:2:stdout",
    "prior:formal_static:2:stderr",
    "prior:formal_static:3:stdout",
    "prior:formal_static:3:stderr",
    "prior:formal_static:4:stdout",
    "prior:formal_static:4:stderr",
    "prior:formal_static:5:stdout",
    "prior:formal_static:5:stderr",
    "prior:formal_static:6:stdout",
    "prior:formal_static:6:stderr",
    "prior:formal_static:7:stdout",
    "prior:formal_static:7:stderr",
    "prior:additional:00",
    "prior:additional:01",
    "prior:additional:02",
    "prior:additional:03",
    "prior:additional:04",
    "prior:additional:05",
    "prior:additional:06",
    "prior:additional:07",
    "prior:additional:08",
    "prior:additional:09",
    "prior:method:root_command_capture",
    "prior:method:root_review_capture",
    "prior:method:ps5_fixture_environment",
    "prior:method:next_owner_guard",
    "custody_candidates:receipt",
    "custody_candidates:stdout.bin",
    "custody_candidates:stderr.bin",
    "custody_candidates:method",
    "custody_audit:receipt",
    "custody_audit:stdout.bin",
    "custody_audit:stderr.bin",
    "custody_audit:method",
    "custody_promotion:receipt",
    "custody_promotion:stdout.bin",
    "custody_promotion:stderr.bin",
    "custody_promotion:method",
    "context_candidate:receipt",
    "context_candidate:stdout.bin",
    "context_candidate:stderr.bin",
    "context_candidate:method",
    "context_audit:receipt",
    "context_audit:stdout.bin",
    "context_audit:stderr.bin",
    "context_audit:method",
    "context_doc_promotion:receipt",
    "context_doc_promotion:stdout.bin",
    "context_doc_promotion:stderr.bin",
    "context_doc_promotion:method",
    "resumed_guard:receipt",
    "resumed_guard:stdout.bin",
    "resumed_guard:stderr.bin",
    "raw_candidate",
    "preflight_candidate",
    "context_candidate_map",
    "prior_proof_roster",
    "custody_signed_go",
    "context_signed_go",
    "custody_promotion_inner",
    "context_doc_promotion_inner",
    "readme_source",
    "reproduction_source",
    "results_source",
    "entry_source",
    "closure_plan",
    "small_map_proposal",
    "resumed_guard_inner",
))

RUNTIME = {"runs", "test-output", "transport-evidence", "__pycache__"}
FIXED_PUBLICATION = {
    "README-publication.md", "REPRODUCTION-postrun.md", "results-summary.json",
    "publication-entry.json", "make_evidence_index.py",
    "review/independent-prelaunch-go.json",
    "review/preflight-ssh0-20261008T224129595Z.json",
    "review/independent-postrun-go.json",
    "review/independent-postrun-scope-go-2026-10-09.md",
    "preserved-raw/raw-originals.json", "preserved-raw/small-copies.json",
    "preserved-raw/raw-000.bytes", "preserved-raw/raw-001.bytes",
    "preserved-preflight/custody.json", "preserved-postrun/custody.json",
}
SMALL = {
    "model-run.log": (782, "2fdeb396c642eb18626084d9db3533d0f71389827fd4fc0066e56c447cd534c2", "preserved-raw/raw-000.bytes"),
    "model.log": (9170, "8b12f53cdb6009c47083d2526f152debe3df341a1fefd8e1df9a46d1b8a47938", "preserved-raw/raw-001.bytes"),
}


def no_reparse(path: Path) -> None:
    assert path.is_absolute(), str(path)
    for part in (path, *path.parents):
        assert not part.is_symlink() and not part.is_junction(), str(part)
        if part.exists():
            assert not (part.stat().st_file_attributes & 0x400), str(part)


def seal(path: Path, *, ro: bool = True) -> dict:
    no_reparse(path)
    assert path.is_file(), str(path)
    if ro:
        assert path.stat().st_file_attributes & 1, str(path)
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def strict_pairs(pairs: list[tuple[str, object]]) -> dict:
    out = {}
    for key, value in pairs:
        assert key not in out, key
        out[key] = value
    return out


def strict_json(data: bytes) -> dict:
    value = json.loads(data, object_pairs_hook=strict_pairs,
                       parse_constant=lambda name: (_ for _ in ()).throw(ValueError(name)))
    assert type(value) is dict
    return value


def pinned(path: Path, pin: tuple[int, str] | None, *, ro: bool = True) -> dict:
    assert pin is not None and len(pin) == 2 and len(pin[1]) == 64, str(path)
    assert seal(path, ro=ro) == {"bytes": pin[0], "sha256": pin[1]}, str(path)
    return strict_json(path.read_bytes())


def integer(value: object, expected: int) -> None:
    assert type(value) is int and value == expected


def typed_equal(left: object, right: object) -> bool:
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return left.keys() == right.keys() and all(typed_equal(left[k], right[k]) for k in left)
    if type(left) is list:
        return len(left) == len(right) and all(typed_equal(a, b) for a, b in zip(left, right))
    return left == right


def frozen_source_checks() -> tuple[dict, dict]:
    inventory = pinned(INVENTORY, INVENTORY_PIN)
    manifest = pinned(MANIFEST, MANIFEST_PIN)
    assert inventory["schema"] == "e02-var02-source-inventory/v104"
    assert manifest["schema"] == "e02-var02-prelaunch-manifest/v104"
    integer(inventory["source_count"], 42)
    integer(manifest["source_count"], 274)
    assert len(inventory["source_files"]) == 42
    assert len(manifest["source_files"]) == 274
    seen = set()
    for row in inventory["source_files"]:
        assert set(row) == {"path", "bytes", "sha256"}
        rel = Path(row["path"])
        assert not rel.is_absolute() and ".." not in rel.parts
        assert str(rel).casefold() not in seen
        seen.add(str(rel).casefold())
        assert seal(CASE / rel) == {"bytes": row["bytes"], "sha256": row["sha256"]}
    keys = set()
    path_pins = {}
    for row in manifest["source_files"]:
        assert set(row) == {"key", "path", "bytes", "sha256"}
        key = row["key"]
        assert type(key) is str and key.casefold() not in keys
        keys.add(key.casefold())
        path = Path(row["path"])
        assert path.is_absolute()
        identity = str(path.resolve(strict=True)).casefold()
        expected = {"bytes": row["bytes"], "sha256": row["sha256"]}
        assert identity not in path_pins or path_pins[identity] == expected
        path_pins[identity] = expected
        assert seal(path, ro=key.startswith("owned:") or key.startswith("excluded-diagnostic-copy:")) == expected
    assert manifest["source_inventory_sha256"] == INVENTORY_PIN[1]
    # The frozen source gate gives direct 39 Git-blob/path pairs, 42 historical
    # originals with original attributes, excluded79/40/26, installed pins,
    # and the typed local/Git catalog-503 prefix. It is source audit only.
    sys.path.insert(0, str(CASE))
    import source_gate  # type: ignore
    before = seal(SOURCE_GATE)
    result = source_gate.verify()
    assert result["passed"] is True and result["native_calls"] == 0
    assert result["accepted_checker_calls"] == 0
    integer(result["accepted_disk_git_pairs"], 39)
    integer(result["mandatory_originals"], 42)
    assert result["excluded_history"] == {
        "excluded_sources": 79,
        "excluded_failed_originals": 40,
        "excluded_diagnostic_copies": 26,
        "semantic_acceptance": False,
    }
    integer(result["historical_original_proofs"], 23)
    assert seal(SOURCE_GATE) == before
    return inventory, manifest


def catalog_check() -> dict:
    selected = pinned(SELECTION, SELECTION_PIN)
    local = pinned(ARCHIVE_LOCAL, ARCHIVE_LOCAL_PIN)
    remote = pinned(ARCHIVE_GIT, ARCHIVE_GIT_PIN)
    assert selected["catalog_local_crlf"] == {"bytes": ARCHIVE_LOCAL_PIN[0], "sha256": ARCHIVE_LOCAL_PIN[1]}
    assert selected["catalog_git_lf"] == {"bytes": ARCHIVE_GIT_PIN[0], "sha256": ARCHIVE_GIT_PIN[1]}
    assert typed_equal(local, remote) and len(local["entries"]) == 503
    current = strict_json(CATALOG.read_bytes())
    assert set(current) == set(local) and len(current["entries"]) >= 503
    for key in local:
        if key not in {"entries", "as_of"}:
            assert typed_equal(current[key], local[key]), key
    for a, b in zip(current["entries"][:503], local["entries"], strict=True):
        assert typed_equal(a, b)
    ids = [row["publication_id"] for row in current["entries"]]
    assert len(ids) == len(set(ids))
    if len(ids) > 503:
        assert ids[503] == PUB_ID
    # Live observations are intentionally excluded from the immutable index body.
    # Reconstructing after the authorized 503->504 append must yield identical bytes.
    return {"baseline_entries": 503,
            "local_crlf": seal(ARCHIVE_LOCAL), "git_lf": seal(ARCHIVE_GIT),
            "baseline_schema": local["schema"],
            "baseline_entry_publication_state": local["entry_publication_state"]}


def custody_check() -> dict:
    raw = pinned(RAW_MAP, RAW_MAP_PIN)
    pre = pinned(PREFLIGHT_MAP, PREFLIGHT_MAP_PIN)
    small = pinned(SMALL_MAP, SMALL_MAP_PIN)
    root = pinned(ROOT_NATIVE, ROOT_NATIVE_PIN)
    root_pre = pinned(ROOT_PREFLIGHT, ROOT_PREFLIGHT_PIN)
    go = pinned(GO, GO_PIN)
    assert seal(GO_SCOPE) == {"bytes": GO_SCOPE_PIN[0], "sha256": GO_SCOPE_PIN[1]}
    assert go["decision"] == "GO_BOUNDED_POSTRUN" and go["run_id"] == RUN_ID
    assert raw["schema"] == "e02-var02-v104-postrun-raw-originals-candidate/v100"
    assert pre["schema"] == "e02-var02-v104-postrun-preflight-originals-candidate/v100"
    integer(raw["mandatory_original_count"], 39)
    integer(raw["recovered_run_copy_count"], 25)
    integer(raw["small_owned_raw_copy_count"], 0)
    integer(pre["mandatory_original_count"], 15)
    assert len(raw["records"]) == 39 and len(pre["records"]) == 15
    assert len(root["originals"]) == 39 and len(root["recovered"]) == 25
    assert len(root_pre["files"]) == 15
    native_seen = set()
    copy_seen = set()
    kinds = {"native_run_original": 0, "native_pure_original": 0,
             "native_transport_original": 0}
    for row in raw["records"]:
        assert set(row) in ({"role", "path", "bytes", "sha256", "mode", "attributes"},
                            {"role", "path", "bytes", "sha256", "mode", "attributes", "recovered_copy"})
        path = Path(row["path"])
        assert str(path) not in native_seen
        native_seen.add(str(path))
        expected = root["originals"][str(path)]
        assert {k: row[k] for k in ("bytes", "sha256", "mode", "attributes")} == expected
        assert seal(path) == {k: row[k] for k in ("bytes", "sha256")}
        assert path.stat().st_mode == row["mode"] and path.stat().st_file_attributes == row["attributes"]
        kinds[row["role"]] += 1
        if "recovered_copy" in row:
            copy = Path(row["recovered_copy"])
            assert row["role"] == "native_run_original"
            assert copy == Path(root["recovered_run"]) / path.name
            assert copy.name not in copy_seen
            copy_seen.add(copy.name)
            assert seal(copy) == root["recovered"][copy.name]
    assert kinds == {"native_run_original": 25, "native_pure_original": 11,
                     "native_transport_original": 3}
    assert native_seen == set(root["originals"]) and copy_seen == set(root["recovered"])
    pre_seen = set()
    for row in pre["records"]:
        assert set(row) == {"path", "bytes", "sha256", "current_mode", "current_attributes"}
        path = Path(row["path"])
        assert str(path) not in pre_seen
        pre_seen.add(str(path))
        assert {k: row[k] for k in ("bytes", "sha256")} == root_pre["files"][str(path)]
        assert seal(path) == root_pre["files"][str(path)]
        assert path.stat().st_mode == row["current_mode"]
        assert path.stat().st_file_attributes == row["current_attributes"]
    assert pre_seen == set(root_pre["files"])
    assert small["schema"] == "e02-var02-v104-small-raw-copies/v100"
    integer(small["small_owned_raw_copy_count"], 2)
    assert small["canonical_original_map"] == "preserved-raw/raw-originals.json"
    assert len(small["records"]) == 2
    names = set()
    owned_paths = set()
    for row in small["records"]:
        name = Path(row["original_path"]).name
        assert name not in names and row["owned_copy"] not in owned_paths
        names.add(name)
        owned_paths.add(row["owned_copy"])
        size, sha, owned = SMALL[name]
        assert row == {"original_path": str(CASE / "runs" / RUN_ID / name),
                       "owned_copy": owned, "bytes": size, "sha256": sha}
        assert seal(CASE / owned) == {"bytes": size, "sha256": sha}
    assert names == set(SMALL)
    assert owned_paths == {entry[2] for entry in SMALL.values()}
    return {"native_originals": 39, "preflight_originals": 15,
            "recovered_copies": 25, "small_owned_raw_copies": 2,
            "raw_map": {"path": str(RAW_MAP), **seal(RAW_MAP)},
            "preflight_map": {"path": str(PREFLIGHT_MAP), **seal(PREFLIGHT_MAP)}}


def context_and_proofs() -> dict:
    assert EXPECTED_CONTEXT_COPIES is not None and PROOF_ROLES is not None
    context = pinned(CONTEXT_MAP, CONTEXT_MAP_PIN)
    assert context["schema"] == "e02-var02-v104-postrun-context-custody/v100"
    integer(context["owned_copy_count"], EXPECTED_CONTEXT_COPIES)
    assert len(context["records"]) == EXPECTED_CONTEXT_COPIES
    seen = set()
    for i, row in enumerate(context["records"]):
        assert set(row) == {"original_path", "owned_copy", "bytes", "sha256", "original_if_present_must_match"}
        assert row["owned_copy"] == f"preserved-postrun/context-{i:03d}.bytes"
        assert row["original_if_present_must_match"] is True
        assert row["original_path"] not in seen
        seen.add(row["original_path"])
        expected = {"bytes": row["bytes"], "sha256": row["sha256"]}
        assert seal(CASE / row["owned_copy"]) == expected
        original = Path(row["original_path"])
        if original.exists():
            assert seal(original) == expected
    proofs = pinned(PROOF_MANIFEST, PROOF_MANIFEST_PIN)
    assert proofs["schema"] == "e02-var02-v104-publication-proof-originals/v100"
    assert proofs["native_dispatch"] is False and proofs["semantic_acceptance"] is False
    assert type(proofs["records"]) is list
    roles = set()
    for row in proofs["records"]:
        assert set(row) == {"role", "path", "bytes", "sha256"}
        assert row["role"].casefold() not in roles
        roles.add(row["role"].casefold())
        path = Path(row["path"])
        assert path.is_relative_to(TMP)
        assert seal(path) == {"bytes": row["bytes"], "sha256": row["sha256"]}
    assert roles == {role.casefold() for role in PROOF_ROLES}
    assert len(proofs["records"]) == len(PROOF_ROLES)
    return {"context_owned_copies": EXPECTED_CONTEXT_COPIES,
            "context_map": {"path": str(CONTEXT_MAP), **seal(CONTEXT_MAP)},
            "publication_proof_originals": len(roles),
            "publication_proof_manifest": {"path": str(PROOF_MANIFEST), **seal(PROOF_MANIFEST)}}


def failed_index_history() -> dict:
    history = pinned(FAILED_INDEX, FAILED_INDEX_PIN)
    assert history["schema"] == "e02-var02-failed-publication-index-custody/v100"
    assert history["native_dispatch"] is False
    assert history["semantic_acceptance"] is False
    assert history["decision"] == "NO_GO_INDEX_CONSTRUCTION_PRESERVED"
    integer(history["actual_exit"], 1)
    assert history["reason"] == "Markdown GO_SCOPE passed to JSON parser; no candidate written"
    assert history["failed_source_original_path"] == str(CASE / "make_evidence_index.py")
    assert history["failed_source_historical_pin"] == FAILED_SOURCE_PIN
    copy = history["failed_source_copy"]
    assert copy == {"path": str(TMP / "e02-var02-failed-index-construction-v103-20261009-01/failed-make_evidence_index-v103.py.bytes"),
                    **FAILED_SOURCE_PIN}
    assert seal(Path(copy["path"])) == FAILED_SOURCE_PIN
    rows = history["frozen_external_originals"]
    assert type(rows) is list and len(rows) == 5
    assert len({row["path"].casefold() for row in rows}) == 5
    for row in rows:
        assert set(row) == {"path", "bytes", "sha256"}
        path = Path(row["path"])
        assert path.is_relative_to(TMP)
        assert seal(path) == {"bytes": row["bytes"], "sha256": row["sha256"]}
    assert rows[-1]["path"] == str(TMP / "e02-var02-publication-author-v104-20261009-01/make_evidence_index_v103.py")
    assert {key: rows[-1][key] for key in ("bytes", "sha256")} == FAILED_SOURCE_PIN
    original = strict_json(Path(rows[0]["path"]).read_bytes())
    assert original["schema"] == "e02-var02-root-command-proof/v104"
    integer(original["actual_exit"], 1)
    assert original["native_dispatch"] is False
    assert original["method_before"] == original["method_after"]
    assert original["streams"]["stdout.bin"] == {key: rows[1][key] for key in ("bytes", "sha256")}
    assert original["streams"]["stderr.bin"] == {key: rows[2][key] for key in ("bytes", "sha256")}
    spec = strict_json(Path(rows[3]["path"]).read_bytes())
    assert spec["schema"] == "e02-var02-root-command-spec/v104"
    assert spec["method"] == str(CASE / "make_evidence_index.py")
    assert spec["method_pin"] == FAILED_SOURCE_PIN
    assert spec["native_dispatch"] is False
    assert spec["arguments"][0] == "--candidate"
    assert not Path(spec["arguments"][1]).exists(), "failed candidate unexpectedly exists"
    return {"decision": "NO_GO_INDEX_CONSTRUCTION_PRESERVED",
            "actual_exit": 1, "native_dispatch": False,
            "custody": {"path": str(FAILED_INDEX), **seal(FAILED_INDEX)},
            "failed_source_copy": copy, "original_proof_file_count": 5}


def closed_sources(context_count: int) -> list[dict]:
    inventory = pinned(INVENTORY, INVENTORY_PIN)
    baseline = {row["path"] for row in inventory["source_files"]}
    baseline |= {"source-inventory.json", "prelaunch-manifest.json"}
    expected = baseline | FIXED_PUBLICATION | {
        f"preserved-postrun/context-{i:03d}.bytes" for i in range(context_count)}
    actual = set()
    for base, dirs, files in os.walk(CASE, followlinks=False):
        here = Path(base)
        no_reparse(here)
        dirs[:] = [name for name in dirs if name not in RUNTIME]
        for name in dirs:
            no_reparse(here / name)
        for name in files:
            rel = (here / name).relative_to(CASE).as_posix()
            if rel == "evidence-index.json":
                continue
            actual.add(rel)
    assert actual == expected, {"unexpected": sorted(actual - expected),
                                "missing": sorted(expected - actual)}
    return [{"path": rel, **seal(CASE / rel)} for rel in sorted(expected)]


def build() -> bytes:
    # The placeholders are a deliberate preflight stop until independent review.
    assert all(pin is not None for pin in (RAW_MAP_PIN, PREFLIGHT_MAP_PIN,
                                           SMALL_MAP_PIN, CONTEXT_MAP_PIN,
                                           PROOF_MANIFEST_PIN))
    assert EXPECTED_CONTEXT_COPIES is not None and PROOF_ROLES is not None
    _, manifest = frozen_source_checks()
    catalog = catalog_check()
    custody = custody_check()
    context = context_and_proofs()
    failed_index = failed_index_history()
    sources = closed_sources(EXPECTED_CONTEXT_COPIES)
    assert len(sources) == 59 + EXPECTED_CONTEXT_COPIES
    result = {
        "schema": "e02-var02-v104-closed-evidence-index/v100",
        "publication_id": PUB_ID,
        "scope_decision": "GO_BOUNDED_POSTRUN",
        "publication_state": "bounded_cli_accepted_for_reusable_publication",
        "new_native_runs": 1,
        "accepted_parent_runs_repeated": 0,
        "physical_log_lines": 123,
        "timed_log_lines": 99,
        "typed_report_cells": 4044,
        "source_count": len(sources),
        "source_files": sources,
        "index_self_excluded": True,
        "frozen_prelaunch": {"owned_sources": 44, "manifest_roles": manifest["source_count"],
                             "accepted_disk_git_pairs": 39, "mandatory_historical_originals": 42,
                             "excluded_v103_sources": 79, "excluded_v103_failed_originals": 40,
                             "excluded_v103_diagnostic_copies": 26},
        "signed_go": {"path": str(GO), **seal(GO)},
        "catalog": catalog,
        "custody": custody,
        "postrun_context": context,
        "excluded_index_construction_history": failed_index,
        "native_dispatch_from_index": False,
        "semantic_checker_dispatch_from_index": False,
    }
    return (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--candidate", type=Path)
    modes.add_argument("--dry", action="store_true")
    args = parser.parse_args()
    body = build()
    digest = hashlib.sha256(body).hexdigest()
    if args.candidate is not None:
        target = args.candidate
        assert target.is_absolute() and target.is_relative_to(TMP)
        assert target != INDEX and target.parent.exists()
        no_reparse(target.parent)
        with target.open("xb") as stream:
            stream.write(body)
        os.chmod(target, 0o444)
        assert seal(target) == {"bytes": len(body), "sha256": digest}
    elif not args.dry:
        assert seal(INDEX) == {"bytes": len(body), "sha256": digest}
    print(json.dumps({"schema": "e02-var02-v104-index-byte-reconstruction/v100",
                      "bytes": len(body), "sha256": digest,
                      "source_count": 59 + EXPECTED_CONTEXT_COPIES,
                      "candidate_created": args.candidate is not None,
                      "native_dispatch": False}, sort_keys=True))


if __name__ == "__main__":
    main()
