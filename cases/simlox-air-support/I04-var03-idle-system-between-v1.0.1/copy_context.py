"""Own the excluded v100 prelaunch history and exact v101 contract context."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from model_common import encode, pin, read, verify_expected

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
DEST = HERE / "preserved-context"
MAP = HERE / "context-custody.json"
V100 = REPO / "tmp/i04-var03-prospective-v101-20261008-01/v100-excluded-history.json"
V100_PIN = {"bytes": 51665, "sha256": "f640cba6258b5a3d252f1c28353ffbc53c0eb3e6394707ea35c346c890d9eb3d"}
FILTERED = REPO / "tmp/i04-var03-case-context-derivatives-v101-20261008-01"
FILTERED_PINS = {
    "transform-map.json": {"bytes": 3352, "sha256": "b2aff8ede267e68333b75921908ac8cacc2d1dca1d7ca9cd3d26b9e948ded135"},
    "case-context-00.json": {"bytes": 126574, "sha256": "bf6af0ca19f1659926e9bdd96e3381ea79603e28c70bbd0295dc79249cce8ef0"},
    "case-context-01.json": {"bytes": 3886, "sha256": "8c00025c1edc5b3528bdb7fadee83dff881ea5423440aa833f548fefe2b5f2c8"},
}
LOCAL_ONLY = (147, 148)
EXTRA = (
    "tmp/i04-var03-prospective-v101-20261008-01/v100-excluded-history.json",
    "tmp/i04-var03-prospective-v101-20261008-01/contract.json",
    "tmp/i04-var03-prospective-v101-20261008-01/selection.json",
    "tmp/i04-var03-prospective-v101-20261008-01/identity-only-proof.json",
    "tmp/i04-var03-prospective-v101-20261008.py",
    "tmp/i04-var03-independent-publication-routing-addendum-20261008.md",
    "tmp/i04-var03-independent-v101-contract-audit-20261008.py",
    "tmp/i04-var03-independent-v101-contract-audit-proof-20261008-01/receipt.json",
    "tmp/i04-var03-independent-v101-contract-audit-proof-20261008-01/stdout.bin",
    "tmp/i04-var03-independent-v101-contract-audit-proof-20261008-01/stderr.bin",
    "tmp/i04-var03-independent-v101-contract-go-20261008.md",
    "tmp/i04-var03-root-v101-method-preparation-20261008.py",
    "tmp/i04-var03-root-v101-method-preparation-20261008.json",
    "tmp/i04-var03-v101-copy-reviewed-template-v1-review-dir-assumption.py.bytes",
    "tmp/i04-var03-v101-copy-reviewed-template-20261008.py",
)


def originals():
    assert pin(V100) == V100_PIN
    history = read(V100)
    assert history["schema"] == "issue18-i04-var03-excluded-prelaunch-history/v1"
    assert len(history["records"]) == 166
    assert history["native_calls"] == 0 and history["actual_case_ssh_preflight_calls"] == 0
    rows = [(Path(row["path"]), {"bytes": row["bytes"], "sha256": row["sha256"]}, "excluded_v100")
            for row in history["records"]]
    for relative in EXTRA:
        path = REPO / relative
        rows.append((path, pin(path), "v101_contract_context"))
    assert len(rows) == 181 and len({str(path.resolve(strict=True)).lower() for path, _, _ in rows}) == 181
    for path, expected, _ in rows:
        assert pin(path) == expected, path
    return rows


def candidate(write=False):
    if not write:
        return {"schema": "i04-var03-v101-context-copy/v2", "records": verify(),
                "map": {"path": str(MAP), **pin(MAP), "exists": True}, "native_calls": 0}
    records = []
    DEST.mkdir(exist_ok=True)
    for number, (source, expected, role) in enumerate(originals()):
        target = DEST / f"context-{number:03d}.bytes"
        if number in LOCAL_ONLY:
            assert not target.exists(), f"private original must not be published: {target}"
            records.append({"original_path": str(source.resolve(strict=True)),
                            "history_index": number, **expected, "role": role,
                            "disposition": "local_only_unrelated_app_context",
                            "original_mandatory": True, "byte_equal_owned_copy": False})
            continue
        body = source.read_bytes()
        verify_expected(target, body, True)
        records.append({"original_path": str(source.resolve(strict=True)),
                        "history_index": number,
                        "owned_copy": target.relative_to(HERE).as_posix(),
                        **expected, "role": role,
                        "disposition": "owned_byte_identical_copy",
                        "original_if_present_must_match": True})
    assert pin(FILTERED / "transform-map.json") == FILTERED_PINS["transform-map.json"]
    transform = read(FILTERED / "transform-map.json")
    assert transform["schema"] == "issue18-i04-var03-app-context-publication-derivatives/v1"
    assert [record["history_index"] for record in transform["records"]] == list(LOCAL_ONLY)
    derivatives = []
    for name in FILTERED_PINS:
        source = FILTERED / name
        expected = FILTERED_PINS[name]
        assert pin(source) == expected
        target = DEST / name
        verify_expected(target, source.read_bytes(), True)
        derivatives.append({"original_path": str(source.resolve(strict=True)),
                            "owned_copy": target.relative_to(HERE).as_posix(),
                            **expected, "disposition": "owned_filtered_derivative",
                            "byte_equal_to_private_original": False})
    mapping = {"schema": "i04-var03-v101-context-custody/v2",
               "excluded_v100_records": 166, "additional_context_records": len(EXTRA),
               "owned_byte_identical_records": 179, "local_only_original_records": 2,
               "local_only_originals_mandatory": True,
               "other_originals_optional_after_publication": True,
               "filtered_derivatives": derivatives, "records": records}
    result = verify_expected(MAP, encode(mapping), True)
    return {"schema": "i04-var03-v101-context-copy/v2", "records": len(records),
            "map": result, "native_calls": 0}


def verify():
    mapping = read(MAP)
    assert mapping["schema"] == "i04-var03-v101-context-custody/v2"
    assert mapping["excluded_v100_records"] == 166
    assert mapping["additional_context_records"] == len(EXTRA)
    assert mapping["owned_byte_identical_records"] == 179
    assert mapping["local_only_original_records"] == 2
    assert mapping["local_only_originals_mandatory"] is True
    assert len(mapping["records"]) == 181
    assert sum(row["role"] == "excluded_v100" for row in mapping["records"]) == 166
    for number, row in enumerate(mapping["records"]):
        assert type(row["history_index"]) is int and row["history_index"] == number
        expected = {"bytes": row["bytes"], "sha256": row["sha256"]}
        source = Path(row["original_path"])
        if number in LOCAL_ONLY:
            assert row["disposition"] == "local_only_unrelated_app_context"
            assert row["original_mandatory"] is True
            assert row["byte_equal_owned_copy"] is False
            assert "owned_copy" not in row
            assert source.exists() and pin(source) == expected
            assert not (DEST / f"context-{number:03d}.bytes").exists()
        else:
            assert row["disposition"] == "owned_byte_identical_copy"
            assert pin(HERE / row["owned_copy"]) == expected
        if source.exists():
            assert pin(source) == expected
    assert len(mapping["filtered_derivatives"]) == 3
    for item, name in zip(mapping["filtered_derivatives"], FILTERED_PINS):
        assert item["owned_copy"] == f"preserved-context/{name}"
        assert {"bytes": item["bytes"], "sha256": item["sha256"]} == FILTERED_PINS[name]
        assert pin(HERE / item["owned_copy"]) == FILTERED_PINS[name]
        source = Path(item["original_path"])
        if source.exists():
            assert pin(source) == FILTERED_PINS[name]
    transform = read(DEST / "transform-map.json")
    assert [item["history_index"] for item in transform["records"]] == list(LOCAL_ONLY)
    for item, name in zip(transform["records"], ("case-context-00.json", "case-context-01.json")):
        assert item["disposition"] == "local_only_unrelated_app_context"
        assert item["byte_equal"] is False
        assert item["derived"] == FILTERED_PINS[name]
        assert pin(Path(item["original_path"])) == item["original"]
    return 181


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    print(json.dumps(candidate(parser.parse_args().write), sort_keys=True))
