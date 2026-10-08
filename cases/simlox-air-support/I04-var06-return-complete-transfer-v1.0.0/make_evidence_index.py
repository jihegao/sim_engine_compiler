"""Build or verify the closed byte index for this bounded classification.

This module reads evidence bytes only. It does not run SIMLOX, the accepted parent
checkers, or either classification reader.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import stat
from pathlib import Path

from author import source_gate


CASE = Path(__file__).resolve().parent
REPO = CASE.parents[2]
INDEX = CASE / "evidence-index.json"
CATALOG = REPO / "cases/simlox-air-support/publication-index-v1.json"
PUB_ID = "I04.var06.return_complete_transfer.1.0.0"
ROOT_MAP = (26280, "3b9ab28af721ca59f4d9388d6118b22f8014004fbdd36ff116bf4f3051c93ece")
REVIEW_V2 = (4454, "db4cfb3061f6759cccf73bec87ca4a1b128f9fbb3981a24ffa056868b7b762cc")
AUTHOR_V1 = (21193, "944992495904c2bae878bc139ec98f9716c705c9e5f277cf346d6e93aeda0a4b")
AUTHOR_V2 = (21199, "ab193256aa3d890cbd1b3eafe52dda7f70aac1945f0ec0c60c47971f86697a36")
WRITER_DIR = REPO / "tmp/i04-var06-root-recovery-proofs-v100-20261008/i04-var06-v100-small-proof-copy-20261008T153209917812Z-fb58487b"
WRITER_ROWS = (
    (WRITER_DIR / "receipt.json", 1397, "af9793ed2fe92856b994ed9748e54421b1c214b5f1681910b75e5da1c5bb0257"),
    (WRITER_DIR / "stdout.bin", 367, "f906aee1bc5a0c8e1c771f29bc1ac6e67160d70a4da69017478a26d1b9063de7"),
    (WRITER_DIR / "stderr.bin", 0, "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"),
    (REPO / "tmp/i04-var06-root-recovery-capture-v100-20261008.py", 1985,
     "8570b723db14e960d4d755bab798f514830f432b750cdd81b292bafa01a0c1dc"),
)
SOURCE_PROVENANCE = (
    ("normalized_connector_record_not_raw_http", REPO / "tmp/i04-var06-root-live-ownership-20261008-01.json",
     12043, "59fa5056b4fc7e6a0ab863028e9a3ceb08e2bd16e0ba37cd9cd2d599fc20d934"),
    ("normalized_connector_record_not_raw_http", REPO / "tmp/i04-var06-root-live-ownership-20261008-02.json",
     21925, "4aaa55c17c63df72766107dfc18bb07c4c0feb3191a065c2f5839a684175b9af"),
    ("historical_selection_input_index", REPO / "tmp/i04-var03-v101-evidence-index-dry-candidate-20261008.json",
     176439, "09e0fe50532797f97d13b3a17fdd886adfc9a18c925038b15058b3850b2273ff"),
    ("installed_manual_local_only", source_gate.MANUAL, 18124110, source_gate.MANUAL_SHA),
    ("installed_dictionary_local_only", source_gate.DICTIONARY, 78577, source_gate.DICTIONARY_SHA),
    ("initial_catalog_local_crlf", source_gate.SELECTION_CAPTURE / "catalog-local-500.json.bytes",
     *source_gate.CATALOG_LOCAL),
    ("initial_catalog_git_lf", source_gate.SELECTION_CAPTURE / "catalog-git-500.json.bytes",
     *source_gate.CATALOG_GIT),
    ("fresh_catalog_local_crlf", REPO / "tmp/i04-var06-root-selection-20261008/20261008T151141226728Z-9cc9c2b4/catalog-local-500.json.bytes",
     *source_gate.CATALOG_LOCAL),
    ("fresh_catalog_git_lf", REPO / "tmp/i04-var06-root-selection-20261008/20261008T151141226728Z-9cc9c2b4/catalog-git-500.json.bytes",
     *source_gate.CATALOG_GIT),
)
AUTHOR_FILES = {
    ".gitattributes", ".gitignore", "contract.json", "contract.md",
    "README-publication.md", "REPRODUCTION-postrun.md", "results-summary.json",
    "publication-entry.json", "make_evidence_index.py",
    "cli-scope-signoff-2026-10-08.md", "cli-scope-signoff-2026-10-08-v2.md",
    "author/build_signature.py", "author/classify.py", "author/classify_v2.py",
    "author/source_gate.py", "tests/self_check.py",
    "source-maps/dependency-pairs.json", "source-maps/event-signature.json",
    "preserved-context/root-selection-receipt.json.bytes",
    "preserved-development/classify-v1-report-attribution-correction.md",
    "preserved-development/classify-v1-wrong-event-count.py.bytes",
    "preserved-development/decoded-development-history.md",
    "preserved-development/self-check-v1-continuation-uniqueness.py.bytes",
}
REVIEW_FILES = {
    "review/independent_classifier.py", "review/independent_self_check.py",
    "review/independent_self_check_v102.py", "review/independent-static-go-2026-10-08.md",
    "review/independent-verdict.json", "review/independent-verdict-v2.json",
    "review/preserved-author-report-attribution-correction.md",
    "review/preserved-independent-selfcheck-v1-before-positive-clone.py.bytes",
    "review/preserved-independent-selfcheck-v101-static-no-go.md",
    "review/preserved-independent-v1-before-source-pin.py.bytes",
    "review/preserved-independent-v2-before-assignment-ledger.py.bytes",
    "review/preserved-independent-verdict-v1-attribution-correction.md",
}


def pin(data: bytes) -> dict[str, object]:
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def exact(path: Path, size: int, digest: str) -> bytes:
    data = path.read_bytes()
    assert pin(data) == {"bytes": size, "sha256": digest}, str(path)
    return data


def decode(data: bytes) -> dict:
    parsed = source_gate.load(data)
    assert type(parsed) is dict
    return parsed


def encode(value: dict) -> bytes:
    return (json.dumps(value, sort_keys=True, indent=2, ensure_ascii=False) + "\n").encode("utf-8")


def proof_custody() -> tuple[list[dict], list[dict]]:
    manifest = decode(exact(CASE / "root-proofs/custody-manifest.json", *ROOT_MAP))
    assert manifest["schema"] == "i04-var06-root-small-proof-custody/v100"
    assert type(manifest["copies_count"]) is int and manifest["copies_count"] == 54
    assert len(manifest["copies"]) == 54
    assert manifest["decision"] == "PASS_SMALL_PROOF_COPIES_ONLY"
    assert manifest["native_calls"] == manifest["accepted_checker_calls"] == 0
    assert manifest["semantic_execution"] is False
    assert manifest["private_app_snapshot_copied"] is False
    assert manifest["native_raw_copied"] is False and manifest["full_manual_copied"] is False
    rows: list[dict] = []
    owned: set[str] = set()
    for row in manifest["copies"]:
        assert set(row) == {"original_path", "owned_path", "bytes", "sha256",
                            "original_mandatory", "original_attributes", "copy_readonly"}
        assert row["original_mandatory"] is True and row["copy_readonly"] is True
        original = Path(row["original_path"])
        rel = row["owned_path"]
        assert original.is_absolute() and original.is_file()
        assert rel.startswith("root-proofs/") and rel not in owned
        owned.add(rel)
        copied = CASE / rel
        assert copied.resolve(strict=True) == copied and not copied.is_symlink() and not copied.is_junction()
        assert not (copied.stat().st_mode & stat.S_IWRITE)
        assert original.stat().st_file_attributes == row["original_attributes"]
        exact(original, row["bytes"], row["sha256"])
        exact(copied, row["bytes"], row["sha256"])
        rows.append({"path": str(original), "owned_copy": rel,
                     "bytes": row["bytes"], "sha256": row["sha256"]})
    assert "root-proofs/053-root-copy-method.py.bytes" in owned
    direct: list[dict] = []
    for path, size, digest in WRITER_ROWS:
        assert path.is_absolute() and path.is_file()
        exact(path, size, digest)
        direct.append({"path": str(path), "bytes": size, "sha256": digest})
    receipt = decode(WRITER_ROWS[0][0].read_bytes())
    assert type(receipt["actual_exit"]) is int and receipt["actual_exit"] == 0
    assert receipt["native_dispatch"] is False
    assert receipt["method_before"] == receipt["method_after"]
    assert receipt["method_before"]["root_capture"] == pin(WRITER_ROWS[3][0].read_bytes())
    assert receipt["method_before"]["review_method"] == pin((CASE / "root-proofs/053-root-copy-method.py.bytes").read_bytes())
    assert receipt["streams"]["stdout.bin"] == pin(WRITER_ROWS[1][0].read_bytes())
    assert receipt["streams"]["stderr.bin"] == pin(WRITER_ROWS[2][0].read_bytes())
    return rows, direct


def raw_custody() -> tuple[list[dict], list[dict]]:
    recovery = decode(exact(source_gate.RECOVERY / "recovery-manifest.json", *source_gate.RECOVERY_MANIFEST))
    assert recovery["copies_count"] == 24 and len(recovery["copies"]) == 24
    original_rows: list[dict] = []
    copy_rows: list[dict] = []
    names: set[str] = set()
    for row in recovery["copies"]:
        name = row["name"]
        assert name not in names
        names.add(name)
        original = Path(row["original_path"])
        copied = Path(row["copy_path"])
        assert original.is_absolute() and copied == source_gate.RECOVERY / "raw" / name
        exact(original, row["bytes"], row["sha256"])
        exact(copied, row["bytes"], row["sha256"])
        assert original.stat().st_mode == row["original_mode_after"] == row["original_mode_before"]
        assert original.stat().st_file_attributes == row["original_attributes_after"] == row["original_attributes_before"]
        assert row["copy_readonly"] is True and not (copied.stat().st_mode & stat.S_IWRITE)
        original_rows.append({"path": str(original), "bytes": row["bytes"],
                              "sha256": row["sha256"], "original_attributes": row["original_attributes_after"]})
        copy_rows.append({"path": str(copied), "bytes": row["bytes"], "sha256": row["sha256"]})
    return original_rows, copy_rows


def source_provenance() -> list[dict]:
    assert len(SOURCE_PROVENANCE) == 9
    rows: list[dict] = []
    for role, path, size, digest in SOURCE_PROVENANCE:
        assert path.is_absolute() and path.is_file()
        exact(path, size, digest)
        rows.append({"role": role, "path": str(path), "bytes": size,
                     "sha256": digest, "host_only": True})
    assert SOURCE_PROVENANCE[5][1].read_bytes() == SOURCE_PROVENANCE[7][1].read_bytes()
    assert SOURCE_PROVENANCE[6][1].read_bytes() == SOURCE_PROVENANCE[8][1].read_bytes()
    assert SOURCE_PROVENANCE[5][1].read_bytes() != SOURCE_PROVENANCE[6][1].read_bytes()
    return rows


def source_rows(root_owned: list[dict]) -> list[dict]:
    expected = AUTHOR_FILES | REVIEW_FILES | {"root-proofs/custody-manifest.json"}
    expected |= {row["owned_copy"] for row in root_owned}
    actual: set[str] = set()
    for path in CASE.rglob("*"):
        if not path.is_file():
            continue
        rel = path.relative_to(CASE).as_posix()
        parts = rel.split("/")
        if rel == "evidence-index.json" or parts[0] == "test-output":
            continue
        if parts[0] == "__pycache__" or (len(parts) >= 2 and parts[-2] == "__pycache__" and path.suffix == ".pyc"):
            continue
        assert rel not in actual and not path.is_symlink() and not path.is_junction(), rel
        actual.add(rel)
    assert len(actual) == len({p.casefold() for p in actual})
    assert actual == expected, {"missing": sorted(expected - actual), "unindexed": sorted(actual - expected)}
    for rel in expected:
        path = CASE / rel
        assert not (path.stat().st_mode & stat.S_IWRITE), f"publishable source is writable: {rel}"
    return [{"path": rel, **pin((CASE / rel).read_bytes())} for rel in sorted(expected)]


def build() -> dict:
    gate = source_gate.verify()
    assert gate["parent_sources"] == 15 and gate["dependency_disk_rows"] == 76
    assert gate["inherited_git_pair_rows"] == 76 and gate["mandatory_originals"] == 24
    assert gate["read_only_copies"] == 24 and gate["catalog_prefix"] == 500
    exact(CASE / "author/classify.py", *AUTHOR_V1)
    original = (CASE / "author/classify.py").read_bytes()
    corrected = exact(CASE / "author/classify_v2.py", *AUTHOR_V2)
    assert corrected == original.replace(b'"full_report_acceptance_inherited"',
                                         b'"bounded_parent_report_checks_inherited"')
    assert original.count(b'"full_report_acceptance_inherited"') == 1
    verdict = decode(exact(CASE / "review/independent-verdict-v2.json", *REVIEW_V2))
    assert verdict["decision"] == "BOUNDED_RETURN_COMPLETE_TRANSFER_CLASSIFICATION"
    assert verdict["new_native_calls"] == 0 and verdict["accepted_parent_checker_reruns"] == 0
    results = decode((CASE / "results-summary.json").read_bytes())
    assert results["decision"] == verdict["decision"] and results["prior_parent_every_report_cell_checked"] is False
    assert results["new_full_report_acceptance"] is False
    entry = decode((CASE / "publication-entry.json").read_bytes())
    assert entry["publication_id"] == PUB_ID and type(entry["new_native_runs"]) is int and entry["new_native_runs"] == 0
    assert type(entry["accepted_parent_runs_repeated"]) is int and entry["accepted_parent_runs_repeated"] == 0
    catalog = decode(CATALOG.read_bytes())
    archive = decode(exact(source_gate.SELECTION_CAPTURE / "catalog-local-500.json.bytes", *source_gate.CATALOG_LOCAL))
    assert source_gate.typed_equal(catalog["entries"][:500], archive["entries"])
    matches = [row for row in catalog["entries"] if row.get("publication_id") == PUB_ID]
    assert (len(catalog["entries"]) == 500 and not matches) or (
        len(catalog["entries"]) >= 501 and len(matches) == 1 and
        source_gate.typed_equal(catalog["entries"][500], entry))
    root_owned, writer = proof_custody()
    raw, copies = raw_custody()
    provenance = source_provenance()
    sources = source_rows(root_owned)
    return {
        "schema": "i04-var06-return-complete-evidence-index/v100",
        "publication_id": PUB_ID, "decision": verdict["decision"],
        "new_native_runs": 0, "accepted_parent_runs_repeated": 0,
        "accepted_parent_checker_reruns": 0,
        "source_count": len(sources), "source_files": sources,
        "mandatory_original_count": len(raw), "mandatory_original_files": raw,
        "recovered_copy_count": len(copies), "recovered_copy_files": copies,
        "parent_indexed_sources": 15, "dependency_disk_and_git_pairs": 76,
        "root_owned_small_proof_count": len(root_owned), "root_owned_small_proofs": root_owned,
        "mandatory_proof_writer_originals": writer,
        "mandatory_host_source_provenance": provenance,
        "parent_bounded_checks": 439, "parent_every_report_cell_checked": False,
        "classification_log_lines": 117, "classification_timed_records": 103,
        "selected_report_numeric_values": 12, "selected_report_row_identities": 4,
        "independent_verdict_v2_sha256": REVIEW_V2[1],
        "corrected_author_classifier_sha256": AUTHOR_V2[1],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry", action="store_true")
    parser.add_argument("--candidate", type=Path)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    assert sum((args.dry, args.candidate is not None, args.write)) <= 1
    body = encode(build())
    if args.write:
        with INDEX.open("xb") as handle:
            handle.write(body)
    elif args.candidate is not None:
        assert args.candidate.is_absolute()
        with args.candidate.open("xb") as handle:
            handle.write(body)
    elif not args.dry:
        assert INDEX.read_bytes() == body
    print(json.dumps({"schema": "i04-var06-evidence-index-builder/v100",
                      "bytes": len(body), "sha256": pin(body)["sha256"],
                      "source_count": json.loads(body)["source_count"],
                      "mandatory_original_count": 24, "recovered_copy_count": 24,
                      "root_owned_small_proof_count": 54,
                      "wrote_canonical": args.write}, sort_keys=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
