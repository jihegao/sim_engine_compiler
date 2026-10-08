"""Reconstruct the closed A17.var06 byte index without semantic/native dispatch.

The independent candidate gate and root-owned canonical promotion are separate.
No mode in this method writes evidence-index.json or runs an accepted checker.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

CASE = Path(r"C:\Users\user\Documents\Codex\2026-09-29\simlox-c04-deadline\repo\cases\simlox-air-support\A17-var06-unit-group-xtime-v1.0.0")
REPO = CASE.parents[2]
TMP = REPO / "tmp"
INDEX = CASE / "evidence-index.json"
INVENTORY = CASE / "source-inventory.json"
MANIFEST = CASE / "prelaunch-manifest.json"
CATALOG = REPO / "cases/simlox-air-support/publication-index-v1.json"
ENTRY = CASE / "publication-entry.json"
GO = CASE / "review/independent-postrun-go.json"
SCOPE = CASE / "cli-scope-signoff-2026-10-09.md"
ROOT_CUSTODY = TMP / "a17-var06-root-native-custody-v100-20261009/20261008T192137549330Z-75862c6d/receipt.json"
ROOT_PREFLIGHT = TMP / "a17-var06-root-actual-preflight-custody-v100-20261009.json"
RAW_CANDIDATE = TMP / "a17-var06-author-postrun-candidates-v102-20261009/raw-custody.json"
PREFLIGHT_CANDIDATE = TMP / "a17-var06-author-postrun-candidates-v102-20261009/preflight-custody.json"
PROOF_MANIFEST = TMP / "a17-var06-publication-proof-originals-v100-20261009.json"
CANDIDATE_ROOT = TMP / "a17-var06-evidence-index-candidates-v100-20261009"
PUB_ID = "A17.var06.unit_group_xtime.1.0.0"

INVENTORY_PIN = (8557, "6b81de61d1b5336312ce370b27f2e6fd00ab2b5fb283581b71a372b8c171f4b7")
MANIFEST_PIN = (72081, "667f1ca78abc1e45909feb1860add2d73e8d4bd8d38aa7adddf47e3765bf4593")
GO_PIN = (2208, "0159453ec9021af0d5de539a29ba6731a898b34e37ec96dcf100922ca19d34e4")
SCOPE_PIN = (2749, "4d7843844c95f4e4fce1bfb2313aa8ebdd00d20b99661b200f66924e42f1880a")
ROOT_CUSTODY_PIN = (19446, "c970a1dc21ab269018a04514a315cb81f7f3d0eb8f470d88560a68bf6103682d")
ROOT_PREFLIGHT_PIN = (6018, "e7326e5d8704ec19bfc5a6e47342c248fee0e95f32b80af42597123dd9ad84fa")
RAW_CANDIDATE_PIN = (21130, "019a11cc5ed877bd8d9bbcc0254fef04e6ef676f5776b98f086cdb43d69d76e1")
PREFLIGHT_CANDIDATE_PIN = (6900, "b1f983f76522cfc4a615c6dc198ac0c23bea0c942a42f1708ca17358cb772974")
CONTEXT_PIN = (68905, "d604f390c3d5e6010bf2f91c81e901e483509edbe2f6220f824255e693242222")
PROOF_PIN = (14318, "3d11460f4e1d09d985e1619c8f618ddc3f8b2f7de99cbefff397fee07cbded2c")

SMALL = {
    "model-run.log": (1052, "5619720783178638b334ffab5d939c9acfd87f34238cc647879534ec5e6c813b", "preserved-raw/raw-000.bytes"),
    "model.log": (4039, "ae6c8430c26490c16e98f7ea66a0137ea7bcd1e309c1f2ba46a44940a0e7f33e", "preserved-raw/raw-001.bytes"),
}
RUNTIME = {"runs", "test-output", "transport-evidence", "__pycache__"}
FUTURE_FIXED = {
    "README-publication.md", "REPRODUCTION-postrun.md", "results-summary.json",
    "publication-entry.json", "make_evidence_index.py", "cli-scope-signoff-2026-10-09.md",
    "review/preflight-ssh0-20261008T191408484Z.json",
    "review/independent-prelaunch-go.json",
    "review/independent-prelaunch-scope-go-2026-10-09.md",
    "review/independent-postrun-go.json",
    "preserved-raw/raw-originals.json", "preserved-raw/small-copies.json",
    "preserved-preflight/custody.json", "preserved-postrun/custody.json",
}
PROOF_ROLES = {
    *(f"{stage}:{stream}" for stage in (
        "postrun_signature_promotion", "raw_custody_candidate",
        "preflight_custody_candidate", "custody_candidate_audit",
        "raw_preflight_promotion", "context_candidate", "context_promotion",
        "postrun_guard", "context_candidate_audit")
      for stream in ("receipt", "stdout", "stderr")),
    "method:custody_builder", "method:custody_auditor",
    "method:raw_preflight_promoter", "method:context_builder",
    "method:context_promoter", "method:root_publication_capture",
    "method:context_auditor", "method:postrun_signature_promoter",
    "method:guard_script", "postrun_signature_promotion:inner_receipt",
    "raw_preflight_promotion:inner_receipt", "context_promotion:inner_receipt",
}


def seal(path: Path, readonly: bool = True) -> dict:
    assert path.is_file() and not path.is_symlink() and not path.is_junction(), str(path)
    if readonly:
        assert path.stat().st_file_attributes & 1, str(path)
    body = path.read_bytes()
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def unique(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        assert key not in result, key
        result[key] = value
    return result


def read(path: Path, expected: tuple[int, str] | None = None,
         readonly: bool = True) -> dict:
    actual = seal(path, readonly)
    if expected is not None:
        assert actual == {"bytes": expected[0], "sha256": expected[1]}, str(path)
    doc = json.loads(path.read_bytes(), object_pairs_hook=unique,
                     parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
    assert type(doc) is dict, str(path)
    return doc


def integer(value: object, expected: int) -> None:
    assert type(value) is int and value == expected


def frozen_sources() -> tuple[dict, dict]:
    inventory = read(INVENTORY, INVENTORY_PIN)
    manifest = read(MANIFEST, MANIFEST_PIN)
    assert inventory["schema"] == "a17-var06-source-inventory/v100"
    assert manifest["schema"] == "a17-var06-prelaunch-manifest/v100"
    integer(inventory["source_count"], 49)
    integer(manifest["source_count"], 193)
    assert len(inventory["source_files"]) == 49 and len(manifest["source_files"]) == 193
    names = set()
    for row in inventory["source_files"]:
        assert set(row) == {"path", "bytes", "sha256"}
        rel = row["path"]
        assert type(rel) is str and rel not in names and not Path(rel).is_absolute()
        assert ".." not in Path(rel).parts
        names.add(rel)
        assert seal(CASE / rel) == {"bytes": row["bytes"], "sha256": row["sha256"]}
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
        expected = {"bytes": row["bytes"], "sha256": row["sha256"]}
        assert identity not in aliases or aliases[identity] == expected
        aliases[identity] = expected
        assert seal(path, readonly=key.startswith("owned:")) == expected
    return inventory, manifest


def raw_and_preflight() -> dict:
    raw_external = read(RAW_CANDIDATE, RAW_CANDIDATE_PIN)
    pre_external = read(PREFLIGHT_CANDIDATE, PREFLIGHT_CANDIDATE_PIN)
    raw_path = CASE / "preserved-raw/raw-originals.json"
    preflight_path = CASE / "preserved-preflight/custody.json"
    assert raw_path.read_bytes() == RAW_CANDIDATE.read_bytes()
    assert preflight_path.read_bytes() == PREFLIGHT_CANDIDATE.read_bytes()
    raw = read(raw_path, RAW_CANDIDATE_PIN)
    preflight = read(preflight_path, PREFLIGHT_CANDIDATE_PIN)
    assert raw == raw_external and preflight == pre_external
    assert raw["schema"] == "a17-var06-postrun-raw-custody-candidate/v102"
    assert preflight["schema"] == "a17-var06-postrun-preflight-custody-candidate/v102"
    integer(raw["mandatory_original_count"], 39)
    integer(raw["recovered_run_copy_count"], 25)
    integer(raw["small_owned_raw_copy_count"], 0)
    integer(preflight["mandatory_original_count"], 15)
    assert len(raw["records"]) == 39 and len(preflight["records"]) == 15
    root = read(ROOT_CUSTODY, ROOT_CUSTODY_PIN)
    root_preflight = read(ROOT_PREFLIGHT, ROOT_PREFLIGHT_PIN)
    assert root["source_roles"] == 193 and len(root["originals"]) == 39
    assert len(root["recovered"]) == 25
    assert root_preflight["native_dispatch"] is False
    assert root_preflight["files_readonly_after"] is True
    assert len(root_preflight["files"]) == 15
    historical_pre = {row["path"]: row for row in root_preflight["files"]}
    roles = {"native_run_original": 0, "native_pure_original": 0,
             "native_transport_original": 0}
    originals = set()
    recovered = set()
    for row in raw["records"]:
        path = Path(row["path"])
        assert path.is_absolute() and str(path) not in originals
        originals.add(str(path))
        role = row["role"]
        if role == "native_run_original":
            roles["native_run_original"] += 1
        elif role in {"native:transport-receipt", "native:ssh-stdout.bin",
                      "native:ssh-stderr.bin"}:
            roles["native_transport_original"] += 1
        else:
            assert role.startswith("native:")
            roles["native_pure_original"] += 1
        expected = root["originals"][str(path)]
        assert seal(path) == {"bytes": row["bytes"], "sha256": row["sha256"]}
        assert path.stat().st_mode == expected["mode"]
        assert path.stat().st_file_attributes == expected["attributes"]
        if row.get("recovered_copy") is not None:
            copy = Path(row["recovered_copy"])
            assert row["role"] == "native_run_original" and copy.name in root["recovered"]
            assert copy == Path(root["recovered_run"]) / path.name
            assert seal(copy) == root["recovered"][path.name]
            assert seal(copy) == {"bytes": row["bytes"], "sha256": row["sha256"]}
            recovered.add(copy.name)
    assert originals == set(root["originals"])
    assert recovered == set(root["recovered"])
    assert roles == {"native_run_original": 25, "native_pure_original": 11,
                     "native_transport_original": 3}
    assert len({row["path"] for row in preflight["records"]}) == 15
    for row in preflight["records"]:
        path = Path(row["path"])
        expected = historical_pre[str(path)]
        assert seal(path) == {"bytes": row["bytes"], "sha256": row["sha256"]}
        assert expected["bytes"] == row["bytes"] and expected["sha256"] == row["sha256"]
        assert expected["original_attributes"] == 32
    small = read(CASE / "preserved-raw/small-copies.json")
    assert small["schema"] == "a17-var06-small-raw-copies/v100"
    integer(small["small_owned_raw_copy_count"], 2)
    integer(small["original_candidate_small_owned_raw_copy_count"], 0)
    assert small["canonical_original_map"] == "preserved-raw/raw-originals.json"
    assert small["original_candidate"] == {"path": str(RAW_CANDIDATE),
                                            **seal(RAW_CANDIDATE)}
    assert type(small["records"]) is list and len(small["records"]) == 2
    for row in small["records"]:
        name = Path(row["original_path"]).name
        size, digest, rel = SMALL[name]
        assert row == {"original_path": str(CASE / "runs/a17-var06-xtime-v100-ssh-20261009-01" / name),
                       "owned_copy": rel, "bytes": size, "sha256": digest}
        assert seal(CASE / rel) == {"bytes": size, "sha256": digest}
    assert {Path(row["original_path"]).name for row in small["records"]} == set(SMALL)
    return {"native_original_count": 39, "preflight_original_count": 15,
            "recovered_copy_count": 25, "small_owned_raw_copy_count": 2,
            "raw_map": {"path": str(CASE / "preserved-raw/raw-originals.json"),
                        **seal(CASE / "preserved-raw/raw-originals.json")},
            "preflight_map": {"path": str(CASE / "preserved-preflight/custody.json"),
                              **seal(CASE / "preserved-preflight/custody.json")}}


def context_rows() -> tuple[dict, list[dict]]:
    assert CONTEXT_PIN is not None and len(CONTEXT_PIN[1]) == 64
    doc = read(CASE / "preserved-postrun/custody.json", CONTEXT_PIN)
    assert doc["schema"] == "a17-var06-postrun-context-custody/v104"
    count = doc["original_count"]
    assert type(count) is int and count == doc["owned_copy_count"] == len(doc["records"]) == 162
    originals = set()
    for index, row in enumerate(doc["records"]):
        assert set(row) == {"original_path", "owned_copy", "bytes", "sha256", "original_if_present_must_match"}
        assert row["owned_copy"] == f"preserved-postrun/context-{index:03d}.bytes"
        assert row["original_if_present_must_match"] is True
        original = Path(row["original_path"])
        assert original.is_absolute() and original not in originals
        assert original.is_relative_to(TMP) or original.is_relative_to(CASE / "test-output")
        originals.add(original)
        expected = {"bytes": row["bytes"], "sha256": row["sha256"]}
        assert seal(CASE / row["owned_copy"]) == expected
        if original.exists():
            assert seal(original) == expected
    return doc, doc["records"]


def publication_proofs() -> dict:
    assert PROOF_PIN is not None and len(PROOF_PIN[1]) == 64
    doc = read(PROOF_MANIFEST, PROOF_PIN)
    assert doc["schema"] == "a17-var06-publication-proof-originals/v100"
    assert type(doc["records"]) is list and len(doc["records"]) == 39
    assert {row["role"] for row in doc["records"]} == PROOF_ROLES
    assert len({row["role"].casefold() for row in doc["records"]}) == 39
    for row in doc["records"]:
        assert set(row) == {"role", "path", "bytes", "sha256"}
        path = Path(row["path"])
        assert path.is_absolute() and path.is_relative_to(TMP)
        assert seal(path) == {"bytes": row["bytes"], "sha256": row["sha256"]}
    return {"manifest": {"path": str(PROOF_MANIFEST), **seal(PROOF_MANIFEST)},
            "mandatory_original_count": 39, "records": doc["records"]}


def case_rows(inventory: dict, context: list[dict]) -> list[dict]:
    expected = {row["path"] for row in inventory["source_files"]}
    assert len(expected) == 49
    expected |= {"source-inventory.json", "prelaunch-manifest.json"}
    expected |= FUTURE_FIXED
    expected |= {item[2] for item in SMALL.values()}
    expected |= {row["owned_copy"] for row in context}
    observed = set()
    for root, dirs, files in os.walk(CASE, topdown=True, followlinks=False):
        at = Path(root)
        if at == CASE:
            for name in dirs:
                assert not (at / name).is_symlink() and not (at / name).is_junction()
            dirs[:] = [name for name in dirs if name not in RUNTIME]
        for name in dirs:
            assert not (at / name).is_symlink() and not (at / name).is_junction()
        for name in files:
            rel = (at / name).relative_to(CASE).as_posix()
            if rel != INDEX.name:
                observed.add(rel)
    assert observed == expected, {"missing": sorted(expected - observed),
                                  "unexpected": sorted(observed - expected)}
    assert len({item.casefold() for item in observed}) == len(observed)
    return [{"path": rel, **seal(CASE / rel)} for rel in sorted(expected)]


def encode(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def build() -> dict:
    inventory, manifest = frozen_sources()
    sys.path.insert(0, str(CASE))
    import source_gate
    gate = source_gate.verify()  # Read-only Git source audit; no checker/native dispatch.
    assert gate["passed"] is True and gate["accepted_disk_git_pairs"] == 59
    assert gate["mandatory_originals"] == 66 and gate["catalog_prefix_entries"] == 502
    go = read(GO, GO_PIN)
    assert go["decision"] == "GO_BOUNDED_POSTRUN" and go["sealed_originals"] == 39
    assert seal(SCOPE) == {"bytes": SCOPE_PIN[0], "sha256": SCOPE_PIN[1]}
    entry = read(ENTRY)
    assert entry["publication_id"] == PUB_ID
    integer(entry["new_native_runs"], 1)
    integer(entry["accepted_parent_runs_repeated"], 0)
    catalog = read(CATALOG, readonly=False)
    matches = [row for row in catalog["entries"] if row.get("publication_id") == PUB_ID]
    assert (len(catalog["entries"]) == 502 and not matches) or (
        len(catalog["entries"]) >= 503 and len(matches) == 1 and
        source_gate.typed_equal(catalog["entries"][502], entry))
    raw = raw_and_preflight()
    context, context_records = context_rows()
    proofs = publication_proofs()
    sources = case_rows(inventory, context_records)
    assert len(sources) == 229
    return {"schema": "a17-var06-bounded-evidence-index/v100", "publication_id": PUB_ID,
            "bounded_decision": go["decision"], "new_native_runs": 1,
            "accepted_parent_runs_repeated": 0, "frozen_prelaunch_owned_sources": 49,
            "frozen_prelaunch_roles": 193, "mandatory_prelaunch_originals": 66,
            "catalog_historical_prefix_entries": 502, "source_count": len(sources),
            "source_files": sources, "raw_and_preflight": raw,
            "postrun_context": {"original_count": context["original_count"],
                                "owned_copy_count": context["owned_copy_count"],
                                "custody_sha256": seal(CASE / "preserved-postrun/custody.json")["sha256"]},
            "mandatory_publication_proof_originals": proofs,
            "observed_primary": {"full_log_lines": 60, "timed_log_lines": 52,
                                 "authored_cells": 203, "exported_cells": 387,
                                 "selected_report_typed_cells": 4966,
                                 "native_commands": 4, "pure_checker_stages": 2,
                                 "physical_log_sha256": "ae6c8430c26490c16e98f7ea66a0137ea7bcd1e309c1f2ba46a44940a0e7f33e",
                                 "selected_report_sha256": "64ce285f79be0b83bd4274f18bb9e63791b3ad09c1023adf5bfec9e0d4c84316"}}


def main() -> None:
    parser = argparse.ArgumentParser()
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--candidate", type=Path)
    modes.add_argument("--dry", action="store_true")
    args = parser.parse_args()
    body = encode(build())
    if args.candidate is not None:
        assert args.candidate.is_absolute() and args.candidate.parent == CANDIDATE_ROOT
        assert CANDIDATE_ROOT.is_dir() and not args.candidate.is_relative_to(CASE)
        with args.candidate.open("xb") as handle:
            handle.write(body)
        args.candidate.chmod(0o444)
    elif not args.dry:
        seal(INDEX)
        assert INDEX.read_bytes() == body, "canonical index differs from byte reconstruction"
    print(json.dumps({"schema": "a17-var06-evidence-index-check/v100",
                      "bytes": len(body), "sha256": hashlib.sha256(body).hexdigest(),
                      "source_count": json.loads(body)["source_count"],
                      "candidate_created": args.candidate is not None}, sort_keys=True))


if __name__ == "__main__":
    main()
