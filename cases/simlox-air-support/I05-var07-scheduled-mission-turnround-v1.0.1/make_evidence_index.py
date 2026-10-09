"""Reconstruct a closed, bounded I05.var07 evidence index from sealed bytes.

The native run, accepted parents, and semantic checkers are never dispatched.
Candidate mode writes one absent file under tmp for independent byte review.
Only root can copy an independently approved candidate into the case.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat

REPO = Path(r"C:\Users\user\Documents\Codex\2026-09-29\simlox-c04-deadline\repo")
TMP = REPO / "tmp"
CASE = REPO / "cases/simlox-air-support/I05-var07-scheduled-mission-turnround-v1.0.1"
CATALOG = REPO / "cases/simlox-air-support/publication-index-v1.json"
INDEX = CASE / "evidence-index.json"
AUTHOR_METHOD = TMP / "i05-var07-publication-author-v101-20261009-01/make_evidence_index.py"
INVENTORY = CASE / "source-inventory.json"
MANIFEST = CASE / "prelaunch-manifest.json"
ROOT54 = TMP / "i05-var07-root-originals-after-freeze-seal-v101-20261009-01.json"
RAW = CASE / "preserved-raw/custody.json"
PREFLIGHT = CASE / "preserved-preflight/custody.json"
CONTEXT = CASE / "preserved-postrun/custody.json"
RAW_CANDIDATE = TMP / "i05-var07-publication-final-raw-custody-candidate-v101-20261009-01.json"
PREFLIGHT_CANDIDATE = TMP / "i05-var07-publication-custody-candidates-v101-20261009-01/preflight-custody.json"
CONTEXT_CANDIDATE = TMP / "i05-var07-publication-context-candidates-v101-20261009-01/context-candidate.json"
PROOF = TMP / "i05-var07-publication-proof-originals-v101-20261009.json"
PROOF_GO = TMP / "i05-var07-independent-proof-manifest-use-go-v101-20261009.json"
PROOF_CAPTURE = TMP / "i05-var07-root-publication-command-proofs-v100-20261009/i05-var07-v101-publication-proof-manifest-20261009T070224140591Z-19e123da"
ARCHIVE_LOCAL = CASE / "source-maps/catalog-local-505.json.bytes"
ARCHIVE_GIT = CASE / "source-maps/catalog-git-505.json.bytes"
GO = CASE / "review/independent-postrun-go.json"
SCOPE = CASE / "review/independent-postrun-scope-2026-10-09.md"
PRECISION = CASE / "review/independent-postrun-scope-precision-2026-10-09.md"
ENTRY = CASE / "publication-entry.json"
PUB_ID = "I05.var07.scheduled_mission_turnround.1.0.1"
RUN_ID = "i05-var07-turnround-v101-ssh-20261009-01"

INVENTORY_PIN = (6598, "7434fce7040e04fc2df4c9fa6ff5db89ced33c93289a9079f1233dd1b59e4072")
MANIFEST_PIN = (58846, "8d94a4def9075796d405f630dda7520e6ef60367668d5bbacd06115249af1d06")
ROOT54_PIN = (28505, "9f53acb320e28b90bb0bbb1f0972d1825a9ddeadc71ec13bc7018bc389f34c62")
LOCAL_PIN = (551394, "3946c8b0e849a2c4fec850e0866b3095a97db235def11682a7108a35bc081539")
GIT_PIN = (546569, "139dae3260e764a90c4f4d228a4fd34eda98c9b6baf17904ff0727ee08fc7fde")
GO_PIN = (1651, "7caaa82b20f14513aa43c0b6b22e79989816a6a8aa854c25e5a83bf1bbd570fd")
SCOPE_PIN = (2956, "df47e99607596e5c8f8f4b167947dcbdb86a14c57f27e7b5f872445604ac58b2")
PRECISION_PIN = (1091, "08e434b98023da6c39cc3885644a3aad866a5df10c47932cedf189562395baaf")
ENTRY_PIN = (2058, "868dd893304f15f2f62ca2b70b568f9c27e9be1ff01697f175d0aab860c9e119")
RAW_PIN = (33643, "6b1c9941a42f26bf0f6bd0542b2d6c33b2263ecea566be50f81872ed7118b40f")
PREFLIGHT_PIN = (9605, "2e045872b5db18315c974fe181123dc268da77368e4cb5df397006eabdc72e2b")
CONTEXT_PIN = (103044, "6badd22101ab2ec2fead299014b43f827e38ff839c25e4bac8f051ff241c607b")
OLD_RAW_PIN = (31327, "a77eb4276f30830a84df752bc6a189f1397518c8409f01727a31c9aae3bde3c0")
SMALL_PROPOSAL_PIN = (1460, "26db83470207bf549bd02c07a638f6ee54617611c09a060e0afd3325f1c554c5")
PROOF_PIN = (135206, "4c1784ba8408f59dbf908186b290b0a0810d1778f83ad27e042f4d6cea361858")
PROOF_GO_PIN = (2440, "5bfdbb053d23a0ebd6e0cb66ca6f4b83189fb9febf6fba3dcd9b63502e1ba29e")
PROOF_RECEIPT_PIN = (1627, "17a869536706864fc41f58b949f3eb9b8db4b022f869f698a011d12fa355ea2a")
PROOF_STDOUT_PIN = (342, "307c1ec05e4f4db783b2b555ef2c4b877fe7a8bb2b9d582a41d5291c9e8a3dd2")
EMPTY_PIN = (0, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855")
PROOF_METHOD_PIN = (12621, "87f32e5c4920c5631dd4dcf30acc842e1c831f31eeafbe14bdec593cd0ccbbee")

SMALL = {
    "model-run.log": (863, "72fd03dc7b22b2c3d2e7b7621d95a9189f5f000855701730124171fa55876680", "preserved-raw/raw-000.bytes"),
    "model.log": (9108, "dc00ee98683714508de8ef483b19d9efc7484c24a08f57886250c902a2c8e445", "preserved-raw/raw-001.bytes"),
}
RUNTIME = {"runs", "test-output", "transport-evidence", "__pycache__"}
FIXED_PUBLICATION = {
    "README-publication.md", "REPRODUCTION-postrun.md", "cli-scope-signoff-2026-10-09.md",
    "results-summary.json", "publication-entry.json", "review/independent-postrun-go.json",
    "review/independent-postrun-scope-2026-10-09.md",
    "review/independent-postrun-scope-precision-2026-10-09.md",
    "review/independent-prelaunch-go.json", "review/independent-prelaunch-scope-2026-10-09.md",
    "review/preflight-ssh0-20261009T054435908Z.json",
    "preserved-raw/custody.json", "preserved-raw/raw-000.bytes", "preserved-raw/raw-001.bytes",
    "preserved-preflight/custody.json", "preserved-postrun/custody.json",
    "make_evidence_index.py",
}
REVIEWED_PINS = {
    "README-publication.md": (4771, "59c1abcfa1da06e6e341db36cc3e5ff7c636a999c13b6cb93af09a58a99e89bb"),
    "REPRODUCTION-postrun.md": (2780, "9a9c0bf0c9d2a6195c855651b4aacfb94f8b8d9063377ac4958006d6e2dda9e8"),
    "cli-scope-signoff-2026-10-09.md": (1661, "b2b810c1c8591d779d6ad4b6a2d7c99c4efbea1daba0e16f43b75458db0073bc"),
    "results-summary.json": (3340, "2e7a22d20996aa90a981daaac68839f43438a21d28a1cb267732e7ae3ca3590c"),
    "publication-entry.json": ENTRY_PIN,
    "review/independent-postrun-go.json": GO_PIN,
    "review/independent-postrun-scope-2026-10-09.md": SCOPE_PIN,
    "review/independent-postrun-scope-precision-2026-10-09.md": PRECISION_PIN,
    "review/independent-prelaunch-go.json": (1184, "98207d3bc891f1254063a647d3bdb3e1159e79f59cfdb540b9c4dfea7937e180"),
    "review/independent-prelaunch-scope-2026-10-09.md": (2968, "e5806cb96172e29231f401ab798187391424ea39ceb5a3bed3282a73e296b799"),
    "review/preflight-ssh0-20261009T054435908Z.json": (49896, "7f8f56d50228d6e11e4ecc8473ffaef5215a7270e57bc534e84fcb6d7d07da50"),
}

def no_reparse(path: Path, *, absent: bool = False) -> None:
    assert path.is_absolute(), str(path)
    if absent:
        assert not path.exists() and not path.is_symlink()
    else:
        assert path.is_file(), str(path)
    for part in (path, *path.parents):
        if part.exists():
            assert not part.is_symlink(), str(part)
            if hasattr(part, "is_junction"):
                assert not part.is_junction(), str(part)
            assert not (getattr(part.stat(), "st_file_attributes", 0) & 0x400), str(part)
    ancestor = path.parent
    while not ancestor.exists():
        assert ancestor != ancestor.parent
        ancestor = ancestor.parent
    if path.is_relative_to(REPO):
        assert ancestor.resolve(strict=True).is_relative_to(REPO.resolve(strict=True))

def seal(path: Path, expected: tuple[int, str] | None = None, *, readonly: bool = True) -> dict:
    no_reparse(path)
    status = path.stat()
    body = path.read_bytes()
    pin = {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}
    if expected is not None:
        assert pin == {"bytes": expected[0], "sha256": expected[1]}, str(path)
    if readonly:
        assert stat.S_IMODE(status.st_mode) == 292
        assert getattr(status, "st_file_attributes", 0) == 33
    return {"path": str(path), **pin, "mode": stat.S_IMODE(status.st_mode),
            "attributes": getattr(status, "st_file_attributes", 0)}

def unique_pairs(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        assert key not in result
        result[key] = value
    return result

def strict_json(path: Path, expected: tuple[int, str] | None = None,
                *, readonly: bool = True) -> dict:
    seal(path, expected, readonly=readonly)
    body = path.read_bytes()
    assert not body.startswith(b"\xef\xbb\xbf")
    result = json.loads(body, object_pairs_hook=unique_pairs,
                        parse_constant=lambda token: (_ for _ in ()).throw(ValueError(token)))
    assert type(result) is dict
    return result

def typed_equal(left: object, right: object) -> bool:
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return left.keys() == right.keys() and all(typed_equal(left[k], right[k]) for k in left)
    if type(left) is list:
        return len(left) == len(right) and all(typed_equal(a, b) for a, b in zip(left, right, strict=True))
    return left == right

def frozen_prelaunch() -> dict:
    inventory = strict_json(INVENTORY, INVENTORY_PIN)
    manifest = strict_json(MANIFEST, MANIFEST_PIN)
    assert inventory["schema"] == "i05-var07-source-inventory/v101"
    assert manifest["schema"] == "i05-var07-prelaunch-manifest/v101"
    assert inventory["source_count"] == len(inventory["source_files"]) == 40
    assert manifest["source_count"] == len(manifest["source_files"]) == 144
    assert manifest["source_inventory_sha256"] == INVENTORY_PIN[1]
    assert manifest["run_id"] == RUN_ID
    assert manifest["owned_source_count"] == 41  # 40 inventoried files plus the inventory itself.
    assert manifest["selected_reference_count"] == 100
    assert manifest["selected_unique_original_count"] == 98
    assert manifest["runtime_source_count"] == 1 and manifest["historical_source_count"] == 2
    owned = set()
    for row in inventory["source_files"]:
        assert set(row) == {"path", "bytes", "sha256"}
        rel = Path(row["path"])
        assert not rel.is_absolute() and ".." not in rel.parts
        ident = rel.as_posix().casefold()
        assert ident not in owned
        owned.add(ident)
        seal(CASE / rel, (row["bytes"], row["sha256"]))
    assert len(owned) == 40
    roles, identities, historical_catalog = set(), {}, 0
    for row in manifest["source_files"]:
        assert set(row) == {"key", "path", "bytes", "sha256", "mode", "attributes"}
        role = row["key"]
        assert role not in roles
        roles.add(role)
        path = Path(row["path"])
        assert path.is_absolute()
        expected = (row["bytes"], row["sha256"])
        if role == "selected:catalog":
            assert path == CATALOG and expected == LOCAL_PIN
            assert row["mode"] == 438 and row["attributes"] == 32
            seal(ARCHIVE_LOCAL, LOCAL_PIN)
            historical_catalog += 1
            continue
        actual = seal(path, expected, readonly=role.startswith("owned:") or role.startswith("historical:"))
        assert actual["mode"] == row["mode"] and actual["attributes"] == row["attributes"], role
        identity = str(path).casefold()
        if identity in identities:
            assert identities[identity] == (expected, row["mode"], row["attributes"])
        else:
            identities[identity] = (expected, row["mode"], row["attributes"])
    assert historical_catalog == 1 and len(roles) == 144
    assert {"owned:" + rel for rel in owned}.issubset({r.casefold() for r in roles})
    return {"owned_sources": 40, "manifest_roles": 144,
            "selected_reference_roles": 100, "selected_unique_originals": 98,
            "historical_live_catalog_role": "selected:catalog",
            "historical_live_catalog_pin": {"bytes": LOCAL_PIN[0], "sha256": LOCAL_PIN[1]},
            "native_source_gate_reexecuted": False}

def catalog_baseline() -> dict:
    local = strict_json(ARCHIVE_LOCAL, LOCAL_PIN)
    git = strict_json(ARCHIVE_GIT, GIT_PIN)
    assert LOCAL_PIN != GIT_PIN and typed_equal(local, git)
    assert local["schema"] == "simlox-air-support-publication-index/v1"
    assert len(local["entries"]) == 505
    current = strict_json(CATALOG, readonly=False)
    assert set(current) == set(local) and len(current["entries"]) >= 505
    for key in local:
        if key not in {"entries", "as_of"}:
            assert typed_equal(current[key], local[key]), key
    assert all(typed_equal(a, b) for a, b in zip(local["entries"], current["entries"][:505], strict=True))
    publication_ids = [row["publication_id"] for row in current["entries"]]
    assert all(type(item) is str and item for item in publication_ids)
    assert len(publication_ids) == len(set(publication_ids))
    entry = strict_json(ENTRY, ENTRY_PIN)
    assert entry["publication_id"] == PUB_ID and entry["observed_child_run"] == RUN_ID
    assert PUB_ID not in {row["publication_id"] for row in local["entries"]}
    if len(publication_ids) > 505:
        assert typed_equal(current["entries"][505], entry)
    # Current live size/as_of is intentionally omitted from immutable index bytes.
    return {"baseline_entries": 505, "baseline_schema": local["schema"],
            "local_crlf": {"path": str(ARCHIVE_LOCAL), "bytes": LOCAL_PIN[0], "sha256": LOCAL_PIN[1]},
            "git_lf": {"path": str(ARCHIVE_GIT), "bytes": GIT_PIN[0], "sha256": GIT_PIN[1]},
            "historical_prelaunch_live_catalog_pin": {"bytes": LOCAL_PIN[0], "sha256": LOCAL_PIN[1]}}

def custody() -> dict:
    raw = strict_json(RAW, RAW_PIN)
    pre = strict_json(PREFLIGHT, PREFLIGHT_PIN)
    root = strict_json(ROOT54, ROOT54_PIN)
    go = strict_json(GO, GO_PIN)
    assert go["decision"] == "GO_BOUNDED_POSTRUN" and go["run_id"] == RUN_ID
    seal(SCOPE, SCOPE_PIN)
    seal(PRECISION, PRECISION_PIN)
    assert RAW.read_bytes() == RAW_CANDIDATE.read_bytes()
    assert PREFLIGHT.read_bytes() == PREFLIGHT_CANDIDATE.read_bytes()
    seal(RAW_CANDIDATE, RAW_PIN)
    seal(PREFLIGHT_CANDIDATE, PREFLIGHT_PIN)
    assert root["schema"] == "i05-var07-root-originals-after-freeze-seal/v101"
    assert len(root["rows"]) == 54 and root["native_original_count"] == 39
    assert root["preflight_original_count"] == 15
    assert raw["schema"] == "i05-var07-v101-raw-custody-final-candidate/v100"
    assert pre["schema"] == "i05-var07-v101-preflight-custody-candidate/v100"
    assert raw["native_dispatch"] is False and pre["native_dispatch"] is False
    assert raw["semantic_acceptance"] is False and pre["semantic_acceptance"] is False
    assert raw["mandatory_original_count"] == len(raw["records"]) == 39
    assert raw["native_directory_count"] == 25 and raw["native_pure_count"] == 11
    assert raw["native_transport_count"] == 3 and raw["recovered_copy_count"] == 25
    assert raw["small_owned_raw_copy_count"] == len(raw["small_owned_raw_copies"]) == 2
    assert pre["mandatory_original_count"] == len(pre["records"]) == 15
    assert pre["pure_count"] == 11 and pre["transport_count"] == 3 and pre["review_count"] == 1
    seen, recovered, counts = set(), set(), {"native_directory": 0, "native_pure": 0, "native_transport": 0}
    for row in raw["records"]:
        path = Path(row["path"])
        assert str(path).casefold() not in seen
        seen.add(str(path).casefold())
        assert row["category"] in counts
        counts[row["category"]] += 1
        actual = seal(path, (row["bytes"], row["sha256"]))
        assert actual["mode"] == row["mode"] == 292 and actual["attributes"] == row["attributes"] == 33
        assert row["pre_freeze_mode"] is None and row["pre_freeze_attributes"] is None
        if "recovered_copy" in row:
            copy = row["recovered_copy"]
            assert row["category"] == "native_directory" and copy["path"] == str(Path(raw["recovered_run_directory"]) / path.name)
            assert path.name not in recovered
            recovered.add(path.name)
            cp = seal(Path(copy["path"]), (copy["bytes"], copy["sha256"]))
            assert cp["bytes"] == row["bytes"] and cp["sha256"] == row["sha256"]
            assert cp["mode"] == copy["mode"] == 292 and cp["attributes"] == copy["attributes"] == 33
    assert counts == {"native_directory": 25, "native_pure": 11, "native_transport": 3}
    assert len(recovered) == 25
    for row in pre["records"]:
        path = Path(row["path"])
        identity = str(path).casefold()
        assert identity not in seen
        seen.add(identity)
        actual = seal(path, (row["bytes"], row["sha256"]))
        assert actual["mode"] == row["mode"] == 292 and actual["attributes"] == row["attributes"] == 33
        assert row["pre_freeze_mode"] is None and row["pre_freeze_attributes"] is None
    root_rows = {row["path"].casefold(): row for row in root["rows"]}
    assert len(root_rows) == len(seen) == 54 and set(root_rows) == seen
    for row in [*raw["records"], *pre["records"]]:
        original = root_rows[row["path"].casefold()]
        assert all(typed_equal(row[key], original[key]) for key in ("bytes", "sha256", "mode", "attributes", "pre_freeze_mode", "pre_freeze_attributes"))
    assert raw["signed_go"] == pre["signed_go"] == {"path": str(GO), "bytes": GO_PIN[0], "sha256": GO_PIN[1]}
    small_names, small_paths = set(), set()
    for row in raw["small_owned_raw_copies"]:
        name = row["name"]
        assert name in SMALL and name not in small_names
        small_names.add(name)
        size, sha, owned = SMALL[name]
        assert row["owned_copy"] == owned and row["bytes"] == size and row["sha256"] == sha
        assert row["native_original"] == str(Path(raw["original_run_directory"]) / name)
        assert row["recovered_original"] == str(Path(raw["recovered_run_directory"]) / name)
        assert owned not in small_paths
        small_paths.add(owned)
        seal(CASE / owned, (size, sha))
        seal(Path(row["native_original"]), (size, sha))
        seal(Path(row["recovered_original"]), (size, sha))
    assert small_names == set(SMALL) and small_paths == {item[2] for item in SMALL.values()}
    return {"native_originals": 39, "native_directory_originals": 25,
            "native_pure_originals": 11, "native_transport_originals": 3,
            "preflight_originals": 15, "recovered_copies": 25, "small_owned_raw_copies": 2,
            "pre_freeze_modes_and_attributes": "unknown_not_inferred",
            "root_after_freeze_seal": {"path": str(ROOT54), "bytes": ROOT54_PIN[0], "sha256": ROOT54_PIN[1]},
            "raw_map": {"path": str(RAW), "bytes": RAW_PIN[0], "sha256": RAW_PIN[1]},
            "preflight_map": {"path": str(PREFLIGHT), "bytes": PREFLIGHT_PIN[0], "sha256": PREFLIGHT_PIN[1]}}

def context_and_proofs() -> dict:
    proof_go = strict_json(PROOF_GO, PROOF_GO_PIN)
    assert proof_go["schema"] == "i05-var07-independent-proof-manifest-use-go/v101"
    assert proof_go["decision"] == "GO_USE_FINITE_PROOF_MANIFEST_AS_BYTE_INPUT_ONLY"
    assert proof_go["proof_manifest"] == {"path": str(PROOF.relative_to(REPO)).replace("\\", "/"),
                                          "bytes": PROOF_PIN[0], "sha256": PROOF_PIN[1],
                                          "schema": "i05-var07-v101-publication-proof-originals/v100",
                                          "unique_original_paths": 303, "unique_roles": 374}
    producer = strict_json(PROOF_CAPTURE / "receipt.json", PROOF_RECEIPT_PIN)
    assert producer["schema"] == "i05-var07-publication-root-command-proof/v100"
    assert producer["actual_exit"] == 0 and producer["native_dispatch"] is False
    assert producer["method_before"] == producer["method_after"]
    assert producer["method_before"]["method"] == {"bytes": PROOF_METHOD_PIN[0], "sha256": PROOF_METHOD_PIN[1]}
    assert producer["argv"][4] == str(TMP / "i05-var07-publication-author-v101-20261009-01/build_publication_proof_manifest.py")
    assert producer["streams"] == {"stdout.bin": {"bytes": PROOF_STDOUT_PIN[0], "sha256": PROOF_STDOUT_PIN[1]},
                                   "stderr.bin": {"bytes": EMPTY_PIN[0], "sha256": EMPTY_PIN[1]}}
    seal(PROOF_CAPTURE / "stdout.bin", PROOF_STDOUT_PIN)
    seal(PROOF_CAPTURE / "stderr.bin", EMPTY_PIN)
    seal(Path(producer["argv"][4]), PROOF_METHOD_PIN)
    context = strict_json(CONTEXT, CONTEXT_PIN)
    assert CONTEXT.read_bytes() == CONTEXT_CANDIDATE.read_bytes()
    seal(CONTEXT_CANDIDATE, CONTEXT_PIN)
    assert context["schema"] == "i05-var07-v101-postrun-context-candidate/v100"
    assert context["original_count"] == len(context["records"]) == 241
    assert context["owned_copy_count"] == 225 and context["host_only_count"] == 16
    assert context["private_mutant_host_only_count"] == 11
    copies, originals = 0, set()
    for row in context["records"]:
        assert set(row) == {"original_path", "bytes", "sha256", "owned_copy", "original_if_present_must_match"}
        assert row["original_if_present_must_match"] is True
        assert row["original_path"] not in originals
        originals.add(row["original_path"])
        expected = (row["bytes"], row["sha256"])
        seal(Path(row["original_path"]), expected)
        if row["owned_copy"] is not None:
            assert row["owned_copy"] == f"preserved-postrun/postrun-{copies:03d}.bytes"
            seal(CASE / row["owned_copy"], expected)
            copies += 1
    assert copies == 225
    proof = strict_json(PROOF, PROOF_PIN)
    assert proof["schema"] == "i05-var07-v101-publication-proof-originals/v100"
    assert proof["native_dispatch"] is False and proof["semantic_acceptance"] is False
    assert proof["prior_context_originals"] == 241
    assert proof["already_indexed_case_sources_skipped"] == 5
    assert proof["prior_tmp_originals"] == 236
    assert proof["late_capture_count"] == 8 and proof["late_guard_count"] == 2
    assert proof["record_count"] == len(proof["records"]) == 303 and proof["role_count"] == 374
    paths, roles = set(), set()
    for row in proof["records"]:
        assert set(row) == {"role", "path", "bytes", "sha256", "mode", "attributes", "aliases"}
        path = Path(row["path"])
        assert path.is_relative_to(TMP) and str(path).casefold() not in paths
        paths.add(str(path).casefold())
        actual = seal(path, (row["bytes"], row["sha256"]))
        assert actual["mode"] == row["mode"] == 292 and actual["attributes"] == row["attributes"] == 33
        for role in [row["role"], *row["aliases"]]:
            assert type(role) is str and role not in roles
            roles.add(role)
    assert len(paths) == 303 and len(roles) == 374
    return {"context_originals": 241, "context_owned_copies": 225,
            "context_host_only_originals": 16, "context_map": {"path": str(CONTEXT), "bytes": CONTEXT_PIN[0], "sha256": CONTEXT_PIN[1]},
            "publication_proof_originals": 303, "publication_proof_roles": 374,
            "publication_proof_manifest": {"path": str(PROOF), "bytes": PROOF_PIN[0], "sha256": PROOF_PIN[1]},
            "independent_proof_use_go": {"path": str(PROOF_GO), "bytes": PROOF_GO_PIN[0], "sha256": PROOF_GO_PIN[1]},
            "proof_producer_original_receipt": {"path": str(PROOF_CAPTURE / "receipt.json"),
                                                "bytes": PROOF_RECEIPT_PIN[0], "sha256": PROOF_RECEIPT_PIN[1]}}

def closed_sources() -> list[dict]:
    inventory = strict_json(INVENTORY, INVENTORY_PIN)
    expected = {row["path"] for row in inventory["source_files"]}
    assert len(expected) == 40
    expected |= {"source-inventory.json", "prelaunch-manifest.json"}
    expected |= FIXED_PUBLICATION
    expected |= {f"preserved-postrun/postrun-{number:03d}.bytes" for number in range(225)}
    assert len(expected) == 284
    actual = set()
    for base, dirs, files in os.walk(CASE, followlinks=False):
        here = Path(base)
        assert here.is_dir() and not here.is_symlink()
        if hasattr(here, "is_junction"):
            assert not here.is_junction()
        assert not (getattr(here.stat(), "st_file_attributes", 0) & 0x400)
        if here == CASE:
            excluded = [name for name in dirs if name in RUNTIME]
            for name in excluded:
                child = here / name
                assert child.is_dir() and not child.is_symlink()
                if hasattr(child, "is_junction"):
                    assert not child.is_junction()
                assert not (getattr(child.stat(), "st_file_attributes", 0) & 0x400)
            dirs[:] = [name for name in dirs if name not in RUNTIME]
        for name in dirs:
            child = here / name
            assert child.is_dir() and not child.is_symlink()
            if hasattr(child, "is_junction"):
                assert not child.is_junction()
            assert not (getattr(child.stat(), "st_file_attributes", 0) & 0x400)
        for name in files:
            rel = (here / name).relative_to(CASE).as_posix()
            if rel != "evidence-index.json":
                actual.add(rel)
    assert actual == expected, {"unexpected": sorted(actual - expected), "missing": sorted(expected - actual)}
    seal(AUTHOR_METHOD)
    assert (CASE / "make_evidence_index.py").read_bytes() == AUTHOR_METHOD.read_bytes()
    for rel, pin in REVIEWED_PINS.items():
        seal(CASE / rel, pin)
    return [{"path": rel, **{key: value for key, value in seal(CASE / rel).items() if key in {"bytes", "sha256"}}}
            for rel in sorted(expected)]

def build() -> bytes:
    before = frozen_prelaunch()
    catalog = catalog_baseline()
    raw = custody()
    context = context_and_proofs()
    sources = closed_sources()
    assert before == frozen_prelaunch()
    assert raw == custody() and context == context_and_proofs()
    body = {"schema": "i05-var07-v101-closed-evidence-index/v100",
            "publication_id": PUB_ID, "scope_decision": "GO_BOUNDED_POSTRUN",
            "publication_state": "bounded_cli_accepted_for_reusable_publication",
            "new_native_runs": 1, "accepted_parent_runs_repeated": 0,
            "authored_typed_cells": 211, "exported_typed_cells": 374,
            "physical_log_lines": 115, "timed_log_lines": 107,
            "typed_report_cells": 4044, "source_count": len(sources),
            "source_files": sources, "index_self_excluded": True,
            "frozen_prelaunch": before,
            "signed_go": {"path": str(GO), "bytes": GO_PIN[0], "sha256": GO_PIN[1]},
            "signed_scope": {"path": str(SCOPE), "bytes": SCOPE_PIN[0], "sha256": SCOPE_PIN[1]},
            "scope_precision_correction": {"path": str(PRECISION), "bytes": PRECISION_PIN[0], "sha256": PRECISION_PIN[1]},
            "catalog": catalog, "custody": raw, "postrun_context": context,
            "native_dispatch_from_index": False,
            "semantic_checker_dispatch_from_index": False}
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
        assert target.is_absolute() and target.is_relative_to(TMP) and target.parent == TMP
        no_reparse(target, absent=True)
        with target.open("xb") as handle:
            handle.write(body)
        os.chmod(target, stat.S_IREAD)
        seal(target, (len(body), digest))
    elif not args.dry:
        seal(INDEX, (len(body), digest))
    print(json.dumps({"schema": "i05-var07-v101-index-byte-reconstruction/v100",
                      "bytes": len(body), "sha256": digest,
                      "source_count": 284, "candidate_created": args.candidate is not None,
                      "native_dispatch": False}, sort_keys=True))

if __name__ == "__main__":
    main()
