"""Preserve small original phase proofs as inert, byte-identical copies.

This script never executes an accepted checker, native command, or reviewer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
ORIGINALS = HERE / "postrun-context-originals.json"
MAP = HERE / "postrun-context-custody.json"
COPY_MAP = HERE / "preserved-postrun/custody.json"
DEV_MAP = HERE / "preserved-postrun-development/custody.json"

# Only case-specific safe proof paths. Native run files, preflight originals and
# private app-context snapshots have separate mandatory original custody.
TREE_PREFIXES = (
    "tmp/i04-var05-v102-author-publication-proofs",
    "tmp/i04-var05-root-guards-v102-20261008",
    "tmp/i04-var05-root-phases-v102-20261008",
    "tmp/i04-var05-root-review-proofs-v102-20261008",
    "tmp/i04-var05-root-sealed-replay-v102-20261008",
    "tmp/i04-var05-root-supplemental-replay-v102-20261008",
    "tmp/i04-var05-root-preflight-seal-v102-20261008",
    "tmp/i04-var05-root-native-transport-seal-v102-20261008",
    "tmp/i04-var05-independent-recovery-contract-proof-v102-revision2-20261008-01",
    "tmp/i04-var05-recovery-design-proof-v102-20261008-01",
    "tmp/i04-var05-recovery-design-proof-v102-revision2-20261008-01",
)
LITERAL_ORIGINALS = (
    "tmp/i04-var05-v102-postrun-receipt-schema-recovery-v1-20261008.json",
    "tmp/i04-var05-v102-independent-postrun-no-go-20261008.md",
    "tmp/i04-var05-v102-independent-supplemental-method-construction-go-20261008.md",
    "tmp/i04-var05-v102-independent-supplemental-method-go-20261008.md",
    "tmp/i04-var05-v102-independent-supplemental-direct-byte-audit-20261008.py",
    "tmp/i04-var05-v102-build-supplemental-reader-20261008.py",
    "tmp/i04-var05-v102-supplemental-receipt-negatives-20261008.py",
    "tmp/i04-var05-v102-supplemental-reader-byte-diff-20261008.json",
    "tmp/i04-var05-v102-independent-actual-preflight-audit-20261008.py",
    "tmp/i04-var05-v102-independent-runtime-hold-20261008.md",
    "tmp/i04-var05-v102-independent-runtime-recovery-20261008.md",
    "tmp/i04-var05-independent-recovery-contract-go-v102-revision2-20261008.md",
    "tmp/i04-var05-independent-recovery-contract-audit-v102-revision2-20261008.py",
    "tmp/i04-var05-independent-recovery-contract-capture-v102-revision2-20261008.py",
    "tmp/i04-var05-recovery-design-v102-20261008.py",
    "tmp/i04-var05-recovery-design-v102-revision2-20261008.py",
    "tmp/i04-var05-recovery-design-capture-v102-20261008.py",
    "tmp/i04-var05-recovery-design-capture-v102-revision2-20261008.py",
    "tmp/i04-var05-root-phase-capture-v102-20261008.py",
    "tmp/i04-var05-root-fresh-guard-v102-20261008.py",
    "tmp/i04-var05-root-review-capture-v102-20261008.py",
    "tmp/i04-var05-root-seal-native-transport-v102-20261008.py",
    "tmp/i04-var05-root-seal-ssh-preflight-v102-20261008.py",
    "tmp/i04-var05-root-sealed-replay-capture-v102-20261008.py",
    "tmp/i04-var05-root-supplemental-replay-capture-v102-20261008.py",
    "tmp/i04-var05-root-catalog-stage-v102-20261008.py",
    "tmp/i04-var05-root-publication-byte-audit-v102-20261008.py",
    "tmp/i04-var05-root-publication-capture-v102-20261008.py",
    "tmp/i04-var05-v102-author-pure-copier-capture-20261008.py",
    "tmp/i04-var05-v102-author-publication-capture-20261008.py",
    "tmp/i04-var05-v102-author-publication-proofs/copy_postrun_context-20261008T105007427638Z/receipt.json",
    "tmp/i04-var05-v102-author-publication-proofs/copy_postrun_context-20261008T105007427638Z/stdout.bin",
    "tmp/i04-var05-v102-author-publication-proofs/copy_postrun_context-20261008T105007427638Z/stderr.bin",
    "tmp/i04-var05-v102-author-publication-proofs/copy_postrun_context-20261008T105007680871Z/receipt.json",
    "tmp/i04-var05-v102-author-publication-proofs/copy_postrun_context-20261008T105007680871Z/stdout.bin",
    "tmp/i04-var05-v102-author-publication-proofs/copy_postrun_context-20261008T105007680871Z/stderr.bin",
    "tmp/i04-var05-root-sealed-replay-v102-20261008/20261008T103341946032Z-fb4f3039/guard-receipt.json",
    "tmp/i04-var05-root-sealed-replay-v102-20261008/20261008T103341946032Z-fb4f3039/guard-stdout.bin",
    "tmp/i04-var05-root-sealed-replay-v102-20261008/20261008T103341946032Z-fb4f3039/guard-stderr.bin",
    "tmp/i04-var05-root-supplemental-replay-v102-20261008/20261008T104257687711Z-edc7361d/guard-receipt.json",
    "tmp/i04-var05-root-supplemental-replay-v102-20261008/20261008T104257687711Z-edc7361d/guard-stdout.bin",
    "tmp/i04-var05-root-supplemental-replay-v102-20261008/20261008T104257687711Z-edc7361d/guard-stderr.bin",
)


def pin(data: bytes) -> dict:
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def encode(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def candidate_paths() -> list[str]:
    paths = set(LITERAL_ORIGINALS)
    for prefix in TREE_PREFIXES:
        base = REPO / prefix
        assert base.is_dir(), prefix
        for path in base.rglob("*"):
            if not path.is_file() or "recovered-evidence" in path.parts:
                continue
            if any(part.startswith("copy_postrun_context-") for part in path.parts):
                continue
            if path.name in ("failure.txt", "receipt.json", "stdout.bin", "stderr.bin",
                             "guard-receipt.json", "guard-stdout.bin", "guard-stderr.bin"):
                paths.add(path.relative_to(REPO).as_posix())
    assert all((REPO / path).is_file() for path in paths)
    assert all("app-context" not in path and "recovered-evidence" not in path for path in paths)
    return sorted(paths)


def prepare() -> dict:
    assert not ORIGINALS.exists()
    rows = [{"original_path": str(REPO / path), "relative_original": path,
             **pin((REPO / path).read_bytes())} for path in candidate_paths()]
    value = {"schema": "i04-var05-v102-postrun-context-originals/v1",
             "records": rows, "originals_optional_after_publication": True,
             "private_app_snapshots_excluded": True,
             "recovered_native_copies_excluded": True}
    ORIGINALS.write_bytes(encode(value))
    return {"records": len(rows), **pin(encode(value))}


def candidate(*, write: bool = False) -> dict:
    source = json.loads(ORIGINALS.read_bytes())
    assert source["schema"] == "i04-var05-v102-postrun-context-originals/v1"
    rows = source["records"]
    assert len(rows) == len({r["relative_original"].casefold() for r in rows})
    expected = []
    for index, row in enumerate(rows):
        assert set(row) == {"original_path", "relative_original", "bytes", "sha256"}
        assert row["relative_original"].startswith("tmp/")
        owned = f"preserved-postrun/postrun-{index:03d}.bytes"
        original = Path(row["original_path"])
        copy = HERE / owned
        if write:
            assert original.is_file()
            data = original.read_bytes()
            assert pin(data) == {k: row[k] for k in ("bytes", "sha256")}
            if not copy.exists():
                copy.parent.mkdir(parents=True, exist_ok=True)
                with copy.open("xb") as out:
                    out.write(data)
        data = copy.read_bytes()
        assert pin(data) == {k: row[k] for k in ("bytes", "sha256")}
        if original.exists():
            assert pin(original.read_bytes()) == pin(data)
        expected.append({"original_path": row["original_path"], "owned_copy": owned,
                         "bytes": row["bytes"], "sha256": row["sha256"],
                         "original_if_present_must_match": True})
    mapping = {"schema": "i04-var05-v102-preserved-postrun-custody/v1",
               "records": expected, "originals_optional_after_publication": True}
    if write:
        assert not COPY_MAP.exists()
        COPY_MAP.write_bytes(encode(mapping))
    else:
        assert COPY_MAP.read_bytes() == encode(mapping)
    summary = {"schema": "i04-var05-v102-postrun-context-custody/v1",
               "records": len(expected), "map_sha256": pin(encode(mapping))["sha256"],
               "originals_optional_after_publication": True}
    if write:
        assert not MAP.exists()
        MAP.write_bytes(encode(summary))
    else:
        assert MAP.read_bytes() == encode(summary)
    return summary


def development(*, write: bool = False) -> dict:
    first_map = json.loads((HERE / "preserved-postrun-development/draft-000.bytes").read_bytes())
    first_rows = first_map["records"]
    failed_dir = HERE / "test-output/failed-context-copy-20261008T105007680871Z"
    assert len(first_rows) == 115
    drafts = []
    for index in range(3):
        path = HERE / f"preserved-postrun-development/draft-{index:03d}.bytes"
        drafts.append({"owned_copy": path.relative_to(HERE).as_posix(), **pin(path.read_bytes())})
    partial = []
    for index in range(96):
        path = failed_dir / f"postrun-{index:03d}.bytes"
        identity = pin(path.read_bytes())
        assert identity == {k: first_rows[index][k] for k in ("bytes", "sha256")}
        partial.append({"path": str(path), **identity, "original_mandatory": True,
                        "first_draft_original_path": first_rows[index]["original_path"]})
    value = {"schema": "i04-var05-v102-postrun-development-custody/v1",
             "failure": "The first context prepare captured its own stdout before the wrapper finished writing it; the first copy stopped at that exact pin mismatch.",
             "first_failed_copy_receipt_sha256": "609e69fe0f8d6edfdece755ccf03d4d07c6976aa1da063de16639b0de621dd8f",
             "first_failure_actual_exit": 1,
             "drafts": drafts, "partial_first_copy_originals": partial,
             "partial_original_count": len(partial),
             "first_failed_receipt_and_streams_owned_in_postrun_context": True}
    data = encode(value)
    if write:
        assert not DEV_MAP.exists()
        DEV_MAP.write_bytes(data)
    else:
        assert DEV_MAP.read_bytes() == data
    return {"schema": value["schema"], "drafts": 3,
            "partial_originals": 96, **pin(data)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--write-development", action="store_true")
    args = parser.parse_args()
    assert sum((args.prepare, args.write, args.write_development)) <= 1
    value = (prepare() if args.prepare else
             development(write=True) if args.write_development else
             candidate(write=args.write))
    print(json.dumps(value, sort_keys=True))


if __name__ == "__main__":
    main()
