"""Reconstruct I05.var04's closed evidence index from reviewed bytes only.

This draft hard-stops until root supplies reviewed custody/context/proof pins.
It never dispatches a native command or semantic checker and never writes the
canonical index. Root alone promotes an independently audited candidate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

REPO = Path(r"C:\Users\user\Documents\Codex\2026-09-29\simlox-c04-deadline\repo")
CASE = REPO / "cases/simlox-air-support/I05-var04-scheduled-item-repair-v1.0.3"
TMP = REPO / "tmp"
INDEX = CASE / "evidence-index.json"
CATALOG = REPO / "cases/simlox-air-support/publication-index-v1.json"
INVENTORY = CASE / "source-inventory.json"
MANIFEST = CASE / "prelaunch-manifest.json"
SOURCE_GATE = CASE / "source_gate.py"
GO = CASE / "review/independent-postrun-go.json"
GO_SCOPE = CASE / "review/independent-postrun-scope-go-2026-10-09.md"
ROOT_NATIVE = TMP / "i05-var04-root-native-custody-v103-20261009/20261009T030153404900Z-922b28c9/receipt.json"
ROOT_PREFLIGHT = TMP / "i05-var04-root-preflight-seal-v103-20261009.json"
RAW_MAP = CASE / "preserved-raw/raw-originals.json"
PREFLIGHT_MAP = CASE / "preserved-preflight/custody.json"
SMALL_MAP = CASE / "preserved-raw/small-copies.json"
CONTEXT_MAP = CASE / "preserved-postrun/custody.json"
PROOF_MANIFEST = TMP / "i05-var04-publication-proof-originals-v103-20261009.json"
ARCHIVE_LOCAL = CASE / "source-maps/catalog-local-504.json.bytes"
ARCHIVE_GIT = CASE / "source-maps/catalog-git-504.json.bytes"
PUB_ID = "I05.var04.scheduled_item_repair.1.0.3"
RUN_ID = "i05-var04-item-repair-v103-ssh-20261009-01"

INVENTORY_PIN = (10146, "6e8ce3f4c9b95ccf4dc8ff14be0e10f798abc3b7e8485e30438e751900116280")
MANIFEST_PIN = (193073, "993a5a2b72a8125c4f78aee0314f1a1180f14fd4f2f6855bf596286462f3e957")
GO_PIN = (2097, "f86bae92b10a88979b3dce0e9d0e117999cd3e385f9fcefde8b0c9d064b379eb")
GO_SCOPE_PIN = (3998, "d445c24c057b31ad8b169bae89e510b62c3a2f0058ac2fb3a8456ce91392f886")
ROOT_NATIVE_PIN = (16960, "4eff235db385fdbb18fb31e34bb28c117da40b865bf30931843ec6dd0433d346")
ROOT_PREFLIGHT_PIN = (5364, "5a49341d50ec4395d1678252ed14d09c2e3265e10dd5a72fc121f61acae7c988")
LOCAL_PIN = (549384, "65856647dd310207447c4621511b9f42da43a9f25e625560d1f56d06762c6985")
GIT_PIN = (544581, "0174772f37e670f1c8e99b65be5acca4870fc3e7dc7ffab24b1d3db73c4735d0")
SMALL = {
    "model-run.log": (782, "40ee4755ca251b6bfe864d4aa0371630bd076dba83df0c9e6245430495ef9949", "preserved-raw/raw-000.bytes"),
    "model.log": (18764, "f5d55db60750c7f1c78d9b73dfe35f4e8d00c01917efc2dd26ec3cc7b42222a1", "preserved-raw/raw-001.bytes"),
}

# Root fills these only after distinct candidate captures, independent byte
# audits, exact case promotions, and fixed proof-manifest review. None may be
# guessed from the native output or a writable scratch file.
RAW_MAP_PIN: tuple[int, str] | None = (22133, "46ad3e25d1e0951d18d69b217642a5a68cd1ab5899772f23f514b2840f08e8bf")
PREFLIGHT_MAP_PIN: tuple[int, str] | None = (7092, "23fda953f1bbc8e5771bb388597f2a52467f0642c3e8de4c509db33d465e4215")
SMALL_MAP_PIN: tuple[int, str] | None = (967, "8657081ff1dd97654eeede7e588d2a1e807e86aae692377863a9de1bf5b1f7e7")
CONTEXT_MAP_PIN: tuple[int, str] | None = (68422, "b48ce755a3c55a103f51473e510e3fbf8450066275bede3a80d3e7073cf1d76d")
PROOF_MANIFEST_PIN: tuple[int, str] | None = (67034, "4d3bbd9172e28cd26aa1340ec012da051863c90eac637ce1af18a57d5a836375")
RAW_CANDIDATE_PIN: tuple[int, str] | None = RAW_MAP_PIN
PREFLIGHT_CANDIDATE_PIN: tuple[int, str] | None = PREFLIGHT_MAP_PIN
CONTEXT_CANDIDATE_PIN: tuple[int, str] | None = CONTEXT_MAP_PIN
RAW_CANDIDATE: Path | None = TMP / "i05-var04-publication-custody-candidates-v103-20261009-01/raw-custody.json"
PREFLIGHT_CANDIDATE: Path | None = TMP / "i05-var04-publication-custody-candidates-v103-20261009-01/preflight-custody.json"
CONTEXT_CANDIDATE: Path | None = TMP / "i05-var04-publication-context-candidate-v103-20261009-01/context-candidate.json"
EXPECTED_CONTEXT_COPIES: int | None = 162
EXPECTED_CONTEXT_ORIGINALS: int | None = 163
PROOF_ROLES: frozenset[str] | None = frozenset((
    "prior:fixed_root_proof_plan",
    "prior:capture:00:receipt",
    "prior:capture:00:stdout.bin",
    "prior:capture:00:stderr.bin",
    "prior:capture:01:receipt",
    "prior:capture:01:stdout.bin",
    "prior:capture:01:stderr.bin",
    "prior:method:capture:01",
    "prior:capture:02:receipt",
    "prior:capture:02:stdout.bin",
    "prior:capture:02:stderr.bin",
    "prior:capture:03:receipt",
    "prior:capture:03:stdout.bin",
    "prior:capture:03:stderr.bin",
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
    "prior:method:capture:14",
    "prior:capture:15:receipt",
    "prior:capture:15:stdout.bin",
    "prior:capture:15:stderr.bin",
    "prior:capture:16:receipt",
    "prior:capture:16:stdout.bin",
    "prior:capture:16:stderr.bin",
    "prior:capture:17:receipt",
    "prior:capture:17:stdout.bin",
    "prior:capture:17:stderr.bin",
    "prior:capture:18:receipt",
    "prior:capture:18:stdout.bin",
    "prior:capture:18:stderr.bin",
    "prior:method:capture:18",
    "prior:capture:19:receipt",
    "prior:capture:19:stdout.bin",
    "prior:capture:19:stderr.bin",
    "prior:capture:20:receipt",
    "prior:capture:20:stdout.bin",
    "prior:capture:20:stderr.bin",
    "prior:capture:21:receipt",
    "prior:capture:21:stdout.bin",
    "prior:capture:21:stderr.bin",
    "prior:method:capture:21",
    "prior:capture:22:receipt",
    "prior:capture:22:stdout.bin",
    "prior:capture:22:stderr.bin",
    "prior:method:capture:22",
    "prior:capture:23:receipt",
    "prior:capture:23:stdout.bin",
    "prior:capture:23:stderr.bin",
    "prior:method:capture:23",
    "prior:capture:24:receipt",
    "prior:capture:24:stdout.bin",
    "prior:capture:24:stderr.bin",
    "prior:method:capture:24",
    "prior:capture:25:receipt",
    "prior:capture:25:stdout.bin",
    "prior:capture:25:stderr.bin",
    "prior:capture:26:receipt",
    "prior:capture:26:stdout.bin",
    "prior:capture:26:stderr.bin",
    "prior:capture:27:receipt",
    "prior:capture:27:stdout.bin",
    "prior:capture:27:stderr.bin",
    "prior:method:capture:27",
    "prior:additional:01",
    "prior:additional:03",
    "prior:additional:05",
    "prior:additional:06",
    "prior:additional:08",
    "prior:additional:09",
    "prior:additional:10",
    "prior:additional:12",
    "prior:additional:14",
    "prior:additional:16",
    "prior:additional:17",
    "prior:additional:19",
    "prior:additional:20",
    "prior:additional:22",
    "prior:additional:24",
    "prior:additional:25",
    "prior:additional:27",
    "prior:additional:29",
    "prior:additional:31",
    "prior:additional:33",
    "prior:additional:34",
    "prior:additional:40",
    "prior:additional:41",
    "prior:additional:42",
    "prior:additional:43",
    "prior:additional:44",
    "prior:additional:45",
    "prior:additional:46",
    "prior:additional:47",
    "prior:additional:48",
    "prior:additional:49",
    "prior:additional:50",
    "prior:additional:51",
    "prior:additional:52",
    "prior:additional:53",
    "prior:additional:54",
    "prior:additional:55",
    "prior:additional:56",
    "prior:additional:57",
    "prior:additional:58",
    "prior:additional:59",
    "prior:additional:60",
    "prior:additional:61",
    "prior:additional:62",
    "prior:additional:63",
    "prior:additional:64",
    "prior:additional:65",
    "prior:additional:66",
    "prior:additional:67",
    "prior:additional:68",
    "prior:additional:69",
    "prior:additional:70",
    "prior:additional:71",
    "prior:additional:72",
    "prior:additional:73",
    "prior:additional:74",
    "prior:additional:75",
    "prior:additional:76",
    "prior:additional:77",
    "custody_candidates:receipt",
    "custody_candidates:stdout.bin",
    "custody_candidates:stderr.bin",
    "custody_candidates:method",
    "context_candidates:receipt",
    "context_candidates:stdout.bin",
    "context_candidates:stderr.bin",
    "context_candidates:method",
    "candidate_audit:receipt",
    "candidate_audit:stdout.bin",
    "candidate_audit:stderr.bin",
    "candidate_audit:method",
    "resumed_guard_outer:receipt",
    "resumed_guard_outer:stdout.bin",
    "resumed_guard_outer:stderr.bin",
    "resumed_guard_inner:receipt",
    "resumed_guard_inner:stdout.bin",
    "resumed_guard_inner:stderr.bin",
    "raw_candidate",
    "preflight_candidate",
    "context_candidate",
    "context_proof_roster",
    "small_map_proposal",
    "source:.gitignore",
    "source:README",
    "source:REPRODUCTION",
    "source:results",
    "source:entry",
    "source:argv_clarification",
    "development:candidate_auditor_r1_unexecuted",
    "development:candidate_auditor_r2_unexecuted",
    "candidate_signed_go",
    "data_promotion:receipt",
    "data_promotion:stdout.bin",
    "data_promotion:stderr.bin",
    "data_promotion:method",
    "data_promotion:inner",
    "method:proof_manifest_builder",
))

RUNTIME = {"runs", "test-output", "transport-evidence", "__pycache__"}
FIXED_PUBLICATION = {
    ".gitignore", "README-publication.md", "REPRODUCTION-postrun.md",
    "results-summary.json", "publication-entry.json", "make_evidence_index.py",
    "review/independent-prelaunch-go.json",
    "review/preflight-ssh0-20261009T025543167Z.json",
    "review/independent-postrun-go.json",
    "review/independent-postrun-scope-go-2026-10-09.md",
    "review/proof-plan-argv-clarification-2026-10-09.md",
    "preserved-raw/raw-originals.json", "preserved-raw/small-copies.json",
    "preserved-raw/raw-000.bytes", "preserved-raw/raw-001.bytes",
    "preserved-preflight/custody.json", "preserved-postrun/custody.json",
}
REVIEWED_PUBLICATION_PINS = {
    ".gitignore": (39, "c1142899b31dc054f15131e50a4507ef502ddaa84882bc407d738a8182671de8"),
    "README-publication.md": (3745, "3e7871a1faecf0b2f0ab8f3258999d118a0fae73af1baa463546963f5a766a43"),
    "REPRODUCTION-postrun.md": (1851, "c200b8e88b6a546223f71255db428e208f6f199846fc62a4b2f471fc5b999c59"),
    "results-summary.json": (2800, "4ddfdf0c6438a6ce600c97a1f7de753096b5f1e5f46511bb458ba7791f35c9e9"),
    "publication-entry.json": (1899, "e61f1ed88bd7f32c2910e037330692755f19721a29219937a6165ad8df1c6c83"),
    "review/proof-plan-argv-clarification-2026-10-09.md": (1501, "33d97274a8dcdff99bd0608b0d94f763ba7690a092db04d9086d40e12db39dc9"),
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
    body = path.read_bytes()
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def unique_pairs(pairs: list[tuple[str, object]]) -> dict:
    value = {}
    for key, item in pairs:
        assert key not in value, key
        value[key] = item
    return value


def strict_json(data: bytes) -> dict:
    value = json.loads(data, object_pairs_hook=unique_pairs,
                       parse_constant=lambda name: (_ for _ in ()).throw(ValueError(name)))
    assert type(value) is dict
    return value


def pinned(path: Path, pin: tuple[int, str] | None, *, ro: bool = True) -> dict:
    assert pin is not None and type(pin[0]) is int and len(pin[1]) == 64
    assert seal(path, ro=ro) == {"bytes": pin[0], "sha256": pin[1]}, str(path)
    return strict_json(path.read_bytes())


def typed_equal(a: object, b: object) -> bool:
    if type(a) is not type(b):
        return False
    if type(a) is dict:
        return a.keys() == b.keys() and all(typed_equal(a[k], b[k]) for k in a)
    if type(a) is list:
        return len(a) == len(b) and all(typed_equal(x, y) for x, y in zip(a, b, strict=True))
    return a == b


def frozen_sources() -> dict:
    inventory = pinned(INVENTORY, INVENTORY_PIN)
    manifest = pinned(MANIFEST, MANIFEST_PIN)
    assert inventory["schema"] == "i05-var04-source-inventory/v103"
    assert manifest["schema"] == "i05-var04-prelaunch-manifest/v103"
    assert type(inventory["source_count"]) is int and inventory["source_count"] == 60
    assert type(manifest["source_count"]) is int and manifest["source_count"] == 546
    assert len(inventory["source_files"]) == 60 and len(manifest["source_files"]) == 546
    owned = set()
    for row in inventory["source_files"]:
        assert set(row) == {"path", "bytes", "sha256"}
        rel = Path(row["path"])
        assert not rel.is_absolute() and ".." not in rel.parts
        identity = rel.as_posix().casefold()
        assert identity not in owned
        owned.add(identity)
        assert seal(CASE / rel) == {"bytes": row["bytes"], "sha256": row["sha256"]}
    roles = set()
    identities = {}
    for row in manifest["source_files"]:
        assert set(row) == {"key", "path", "bytes", "sha256"}
        role = row["key"].casefold()
        assert role not in roles
        roles.add(role)
        path = Path(row["path"])
        assert path.is_absolute()
        identity = str(path.resolve(strict=True)).casefold()
        expected = {"bytes": row["bytes"], "sha256": row["sha256"]}
        assert identity not in identities or identities[identity] == expected
        identities[identity] = expected
        assert seal(path, ro=row["key"].startswith("owned:") or row["key"].startswith("excluded-diagnostic-copy:")) == expected
    assert manifest["source_inventory_sha256"] == INVENTORY_PIN[1]
    before = seal(SOURCE_GATE)
    sys.path.insert(0, str(CASE))
    import source_gate  # type: ignore
    gate = source_gate.verify()
    assert seal(SOURCE_GATE) == before
    assert gate["schema"] == "i05-var04-source-gate/v103" and gate["passed"] is True
    assert gate["native_calls"] == gate["accepted_checker_calls"] == 0
    assert gate["accepted_disk_git_pairs"] == 21
    assert gate["accepted_parent_raw_originals"] == 12
    assert gate["accepted_parent_verdict_invocation_closure"] == 3
    assert [gate[f"excluded_v{v}_history_roles"] for v in (100, 101, 102)] == [64, 112, 269]
    assert gate["catalog_prefix_entries"] == 504
    return {"owned_sources": 60, "manifest_roles": 546,
            "accepted_disk_git_pairs": 21, "accepted_parent_raw_originals": 12,
            "accepted_parent_acceptance_context": 3,
            "excluded_history_roles": {"v100": 64, "v101": 112, "v102": 269},
            "raw_attribute_basis": "current_observation_only"}


def catalog_baseline() -> dict:
    local = pinned(ARCHIVE_LOCAL, LOCAL_PIN)
    git = pinned(ARCHIVE_GIT, GIT_PIN)
    assert typed_equal(local, git) and len(local["entries"]) == 504
    current = strict_json(CATALOG.read_bytes())
    assert set(current) == set(local) and len(current["entries"]) >= 504
    for key in local:
        if key not in {"entries", "as_of"}:
            assert typed_equal(current[key], local[key]), key
    assert all(typed_equal(a, b) for a, b in zip(local["entries"], current["entries"][:504], strict=True))
    ids = [row["publication_id"] for row in current["entries"]]
    assert len(ids) == len(set(ids))
    if len(ids) > 504:
        assert ids[504] == PUB_ID
        published_entry = strict_json((CASE / "publication-entry.json").read_bytes())
        assert typed_equal(current["entries"][504], published_entry)
    # Live append state is checked but omitted from immutable index bytes.
    return {"baseline_entries": 504, "local_crlf": seal(ARCHIVE_LOCAL),
            "git_lf": seal(ARCHIVE_GIT), "baseline_schema": local["schema"],
            "baseline_entry_publication_state": local["entry_publication_state"]}


def custody() -> dict:
    assert all(item is not None for item in (RAW_CANDIDATE, PREFLIGHT_CANDIDATE,
                                             RAW_CANDIDATE_PIN, PREFLIGHT_CANDIDATE_PIN))
    raw = pinned(RAW_MAP, RAW_MAP_PIN)
    pre = pinned(PREFLIGHT_MAP, PREFLIGHT_MAP_PIN)
    small = pinned(SMALL_MAP, SMALL_MAP_PIN)
    assert RAW_MAP.read_bytes() == RAW_CANDIDATE.read_bytes()
    assert PREFLIGHT_MAP.read_bytes() == PREFLIGHT_CANDIDATE.read_bytes()
    pinned(RAW_CANDIDATE, RAW_CANDIDATE_PIN)
    pinned(PREFLIGHT_CANDIDATE, PREFLIGHT_CANDIDATE_PIN)
    root = pinned(ROOT_NATIVE, ROOT_NATIVE_PIN)
    root_pre = pinned(ROOT_PREFLIGHT, ROOT_PREFLIGHT_PIN)
    go = pinned(GO, GO_PIN)
    assert seal(GO_SCOPE) == {"bytes": GO_SCOPE_PIN[0], "sha256": GO_SCOPE_PIN[1]}
    assert go["decision"] == "GO_BOUNDED_POSTRUN" and go["run_id"] == RUN_ID
    assert raw["schema"] == "i05-var04-v103-postrun-raw-originals-candidate/v100"
    assert pre["schema"] == "i05-var04-v103-postrun-preflight-originals-candidate/v100"
    assert len(raw["records"]) == raw["mandatory_original_count"] == 39
    assert raw["recovered_run_copy_count"] == 25 and raw["small_owned_raw_copy_count"] == 0
    assert len(pre["records"]) == pre["mandatory_original_count"] == 15
    assert len(root["originals"]) == 39 and len(root["recovered"]) == 25
    assert len(root_pre["files"]) == 15
    seen_native = set()
    seen_copy = set()
    kinds = {"native_run_original": 0, "native_pure_original": 0,
             "native_transport_original": 0}
    for row in raw["records"]:
        assert set(row) in ({"role", "path", "bytes", "sha256", "mode", "attributes"},
                            {"role", "path", "bytes", "sha256", "mode", "attributes", "recovered_copy"})
        path = Path(row["path"])
        assert str(path) not in seen_native and str(path) in root["originals"]
        seen_native.add(str(path))
        expected = root["originals"][str(path)]
        assert {k: row[k] for k in ("bytes", "sha256", "mode", "attributes")} == expected
        assert seal(path) == {k: row[k] for k in ("bytes", "sha256")}
        assert path.stat().st_mode == row["mode"] and path.stat().st_file_attributes == row["attributes"]
        assert row["role"] in kinds
        kinds[row["role"]] += 1
        if "recovered_copy" in row:
            copy = Path(row["recovered_copy"])
            assert row["role"] == "native_run_original"
            assert copy == Path(root["recovered_run"]) / path.name
            assert copy.name not in seen_copy
            seen_copy.add(copy.name)
            assert seal(copy) == root["recovered"][copy.name]
    assert seen_native == set(root["originals"]) and seen_copy == set(root["recovered"])
    assert kinds == {"native_run_original": 25, "native_pure_original": 11,
                     "native_transport_original": 3}
    seen_pre = set()
    for row in pre["records"]:
        assert set(row) == {"path", "bytes", "sha256", "current_mode", "current_attributes"}
        path = Path(row["path"])
        assert str(path) not in seen_pre and str(path) in root_pre["files"]
        seen_pre.add(str(path))
        assert {k: row[k] for k in ("bytes", "sha256")} == root_pre["files"][str(path)]
        assert seal(path) == root_pre["files"][str(path)]
        assert path.stat().st_mode == row["current_mode"]
        assert path.stat().st_file_attributes == row["current_attributes"]
    assert seen_pre == set(root_pre["files"])
    assert small["schema"] == "i05-var04-v103-small-raw-copies/v100"
    assert small["small_owned_raw_copy_count"] == 2 and len(small["records"]) == 2
    assert small["canonical_original_map"] == "preserved-raw/raw-originals.json"
    names = set()
    paths = set()
    for row in small["records"]:
        name = Path(row["original_path"]).name
        assert name in SMALL and name not in names and row["owned_copy"] not in paths
        names.add(name)
        paths.add(row["owned_copy"])
        size, sha, owned = SMALL[name]
        assert row == {"original_path": str(CASE / "runs" / RUN_ID / name),
                       "owned_copy": owned, "bytes": size, "sha256": sha}
        assert seal(CASE / owned) == {"bytes": size, "sha256": sha}
    assert names == set(SMALL) and paths == {item[2] for item in SMALL.values()}
    return {"native_originals": 39, "preflight_originals": 15,
            "recovered_copies": 25, "small_owned_raw_copies": 2,
            "raw_map": {"path": str(RAW_MAP), **seal(RAW_MAP)},
            "preflight_map": {"path": str(PREFLIGHT_MAP), **seal(PREFLIGHT_MAP)}}


def context_and_proofs() -> dict:
    assert all(item is not None for item in (CONTEXT_CANDIDATE, CONTEXT_CANDIDATE_PIN,
                                             CONTEXT_MAP_PIN, PROOF_MANIFEST_PIN,
                                             EXPECTED_CONTEXT_COPIES,
                                             EXPECTED_CONTEXT_ORIGINALS, PROOF_ROLES))
    context = pinned(CONTEXT_MAP, CONTEXT_MAP_PIN)
    pinned(CONTEXT_CANDIDATE, CONTEXT_CANDIDATE_PIN)
    assert CONTEXT_MAP.read_bytes() == CONTEXT_CANDIDATE.read_bytes()
    assert context["schema"] == "i05-var04-v103-postrun-context-custody-candidate/v100"
    assert context["owned_copy_count"] == EXPECTED_CONTEXT_COPIES
    assert context["original_count"] == EXPECTED_CONTEXT_ORIGINALS
    assert len(context["records"]) == EXPECTED_CONTEXT_ORIGINALS
    copies = 0
    originals = set()
    for row in context["records"]:
        assert set(row) == {"original_path", "owned_copy", "bytes", "sha256",
                            "original_if_present_must_match"}
        assert row["original_if_present_must_match"] is True
        assert row["original_path"] not in originals
        originals.add(row["original_path"])
        expected = {"bytes": row["bytes"], "sha256": row["sha256"]}
        original = Path(row["original_path"])
        assert original.exists() and seal(original) == expected
        if row["owned_copy"] is None:
            assert row["bytes"] > 200_000
        else:
            assert row["owned_copy"] == f"preserved-postrun/context-{copies:03d}.bytes"
            assert row["bytes"] <= 200_000
            assert seal(CASE / row["owned_copy"]) == expected
            copies += 1
    assert copies == EXPECTED_CONTEXT_COPIES
    proof = pinned(PROOF_MANIFEST, PROOF_MANIFEST_PIN)
    assert proof["schema"] == "i05-var04-v103-publication-proof-originals/v100"
    assert proof["native_dispatch"] is False and proof["semantic_acceptance"] is False
    assert proof["prior_roster_originals"] == 163
    assert proof["prior_canonical_sources_skipped"] == 8
    assert proof["prior_tmp_originals"] == 155
    assert proof["record_count"] == 193 and len(proof["records"]) == 193
    roles = set()
    paths = set()
    for row in proof["records"]:
        assert set(row) == {"role", "path", "bytes", "sha256"}
        assert type(row["role"]) is str
        role = row["role"].casefold()
        assert role not in roles
        roles.add(role)
        path = Path(row["path"])
        assert path.is_relative_to(TMP)
        identity = str(path.resolve(strict=True)).casefold()
        assert identity not in paths
        paths.add(identity)
        assert seal(path) == {"bytes": row["bytes"], "sha256": row["sha256"]}
    assert roles == {role.casefold() for role in PROOF_ROLES}
    assert len(proof["records"]) == len(PROOF_ROLES)
    return {"context_owned_copies": copies, "context_host_only_originals": len(originals) - copies,
            "context_map": {"path": str(CONTEXT_MAP), **seal(CONTEXT_MAP)},
            "publication_proof_originals": len(roles),
            "publication_proof_manifest": {"path": str(PROOF_MANIFEST), **seal(PROOF_MANIFEST)}}


def closed_sources(context_count: int) -> list[dict]:
    inventory = pinned(INVENTORY, INVENTORY_PIN)
    expected = {row["path"] for row in inventory["source_files"]}
    expected |= {"source-inventory.json", "prelaunch-manifest.json"}
    expected |= FIXED_PUBLICATION
    expected |= {f"preserved-postrun/context-{i:03d}.bytes" for i in range(context_count)}
    actual = set()
    for base, dirs, files in os.walk(CASE, followlinks=False):
        here = Path(base)
        no_reparse(here)
        if here == CASE:
            dirs[:] = [name for name in dirs if name not in RUNTIME]
        for name in dirs:
            no_reparse(here / name)
        for name in files:
            rel = (here / name).relative_to(CASE).as_posix()
            if rel != "evidence-index.json":
                actual.add(rel)
    assert actual == expected, {"unexpected": sorted(actual - expected),
                                "missing": sorted(expected - actual)}
    for rel, pin in REVIEWED_PUBLICATION_PINS.items():
        assert seal(CASE / rel) == {"bytes": pin[0], "sha256": pin[1]}, rel
    return [{"path": rel, **seal(CASE / rel)} for rel in sorted(expected)]


def build() -> bytes:
    required = (RAW_MAP_PIN, PREFLIGHT_MAP_PIN, SMALL_MAP_PIN, CONTEXT_MAP_PIN,
                PROOF_MANIFEST_PIN, RAW_CANDIDATE, PREFLIGHT_CANDIDATE,
                CONTEXT_CANDIDATE, RAW_CANDIDATE_PIN, PREFLIGHT_CANDIDATE_PIN,
                CONTEXT_CANDIDATE_PIN, EXPECTED_CONTEXT_COPIES,
                EXPECTED_CONTEXT_ORIGINALS, PROOF_ROLES)
    assert all(item is not None for item in required), "reviewed publication pins pending"
    prelaunch = frozen_sources()
    catalog = catalog_baseline()
    raw = custody()
    context = context_and_proofs()
    sources = closed_sources(EXPECTED_CONTEXT_COPIES)
    assert len(sources) == 79 + EXPECTED_CONTEXT_COPIES
    body = {
        "schema": "i05-var04-v103-closed-evidence-index/v100",
        "publication_id": PUB_ID,
        "scope_decision": "GO_BOUNDED_POSTRUN",
        "publication_state": "bounded_cli_accepted_for_reusable_publication",
        "new_native_runs": 1, "accepted_parent_runs_repeated": 0,
        "physical_log_lines": 222, "timed_log_lines": 186,
        "typed_report_cells": 4044,
        "source_count": len(sources), "source_files": sources,
        "index_self_excluded": True,
        "frozen_prelaunch": prelaunch,
        "signed_go": {"path": str(GO), **seal(GO)},
        "catalog": catalog, "custody": raw, "postrun_context": context,
        "native_dispatch_from_index": False,
        "semantic_checker_dispatch_from_index": False,
    }
    return (json.dumps(body, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


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
    print(json.dumps({"schema": "i05-var04-v103-index-byte-reconstruction/v100",
                      "bytes": len(body), "sha256": digest,
                      "source_count": 79 + EXPECTED_CONTEXT_COPIES,
                      "candidate_created": args.candidate is not None,
                      "native_dispatch": False}, sort_keys=True))


if __name__ == "__main__":
    main()
