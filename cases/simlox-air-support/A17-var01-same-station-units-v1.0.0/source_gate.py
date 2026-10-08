"""Read-only, append-stable source custody for the bounded A17.var01 child."""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
PINS = HERE / "source-maps/prospective-source-pins.json"
PAIRS = HERE / "source-maps/accepted-source-pairs.json"
SELECTION = HERE / "preserved-context/root-selection-receipt.json"
CONTRACT = HERE / "prospective-contract.json"
REPORT = HERE / "prospective-report-oracle.json"
LOG_FORMS = HERE / "prospective-complete-log-forms.json"
PARENT_CATALOG = REPO / "cases/simlox-air-support/publication-index-v1.json"
CONVERTER_NEGATIVE = REPO / "cases/simlox-air-support/I04-var05-zero-transport-between-v1.0.0/runs/i04-var05-zero-transport-between-v100-ssh-20261008-01/model-run.log"
CONVERTER_NEGATIVE_PIN = {"bytes": 1122, "sha256": "ca209899bce7e299b49d9a482469efd8c0fee0d9f56673ffb99783cbf689457a"}
INSTALLED_EXE = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
INSTALLED_EXE_PIN = {"bytes": 33196032, "sha256": "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"}
PYTHON_RUNTIME = Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
PYTHON_RUNTIME_PIN = {"bytes": 106448, "sha256": "10d845f50a2af64e3500bb2fcb348b5bc98a75d8ddada63e45ba1da6a1fc79d1"}
PINNED_SOURCE_SHA = "65a64eba90bebc6efe31f186fd7108528529ab07caadd5e9f17afd567f878680"
PINNED_PAIRS_SHA = "e622b47972ab740dedc1208e7dcc85ea50432b5ee7744d12cbbfc44829a00bf2"
PINNED_SELECTION_SHA = "75a009a4754a842604bc96d588a5ac5a896d1cde8028768b53e93e16e7f9f7ea"
PINNED_CONTRACT_SHA = "d878f097ca7f021982628691a1c61c8b64633bc235de6fd9c8b116da587aed0b"
PINNED_REPORT_SHA = "3ae5e69163f8d211afc23de49346c2cd2ca87a7ca80fb825831ed0cedd291c7b"
PINNED_FORMS_SHA = "71eeec318ba6b7bd5b19a527891b5fd3125b7d66e7d59c9a30f41314ecad8c32"


def seal(path: Path) -> dict:
    body = path.read_bytes()
    return {"bytes": len(body), "sha256": hashlib.sha256(body).hexdigest()}


def exact(path: Path, pin: dict) -> None:
    got = seal(path)
    assert got["bytes"] == pin["bytes"] and got["sha256"] == pin["sha256"], str(path)


def owned(path: Path, digest: str) -> None:
    assert seal(path)["sha256"] == digest, str(path)


def typed_equal(a: object, b: object) -> bool:
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return list(a) == list(b) and all(typed_equal(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(typed_equal(x, y) for x, y in zip(a, b, strict=True))
    return a == b


def strict_catalog(path: Path) -> dict:
    def unique_pairs(pairs: list[tuple[str, object]]) -> dict:
        result = {}
        for key, value in pairs:
            assert key not in result, f"duplicate catalog key: {key}"
            result[key] = value
        return result
    def reject_constant(value: str) -> None:
        raise AssertionError(f"nonfinite catalog value: {value}")
    result = json.loads(path.read_bytes().decode("utf-8-sig"),
                        object_pairs_hook=unique_pairs, parse_constant=reject_constant)
    assert type(result) is dict
    return result


def git_batch(pairs: list[dict], base: str) -> None:
    oids = [row["oid"] for row in pairs]
    assert len(oids) == len(set(oids))
    paths = [row["path"] for row in pairs]
    tree = subprocess.run(
        ["git", "ls-tree", "-r", "-z", base, "--", *paths],
        cwd=REPO, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
    )
    assert tree.stderr == b""
    observed = {}
    for record in tree.stdout.split(b"\0"):
        if not record:
            continue
        header, path = record.split(b"\t", 1)
        mode, kind, oid = header.decode("ascii").split(" ")
        name = path.decode("utf-8")
        assert kind == "blob" and name not in observed
        observed[name] = (mode, oid)
    assert set(observed) == set(paths)
    for row in pairs:
        assert observed[row["path"]][1] == row["oid"]
    command = subprocess.run(
        ["git", "cat-file", "--batch"], cwd=REPO,
        input=("\n".join(oids) + "\n").encode("ascii"),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True,
    )
    assert command.stderr == b""
    buf = command.stdout
    pos = 0
    for row in pairs:
        end = buf.find(b"\n", pos)
        assert end >= 0
        header = buf[pos:end].decode("ascii").split(" ")
        assert len(header) == 3 and header[0] == row["oid"] and header[1] == "blob"
        size = int(header[2])
        start = end + 1
        blob = buf[start:start + size]
        assert len(blob) == size and buf[start + size:start + size + 1] == b"\n"
        assert size == row["git"]["bytes"]
        assert hashlib.sha256(blob).hexdigest() == row["git"]["sha256"]
        pos = start + size + 1
    assert pos == len(buf)


def verify() -> dict:
    owned(PINS, PINNED_SOURCE_SHA)
    owned(PAIRS, PINNED_PAIRS_SHA)
    owned(SELECTION, PINNED_SELECTION_SHA)
    owned(CONTRACT, PINNED_CONTRACT_SHA)
    owned(REPORT, PINNED_REPORT_SHA)
    owned(LOG_FORMS, PINNED_FORMS_SHA)
    pins = json.loads(PINS.read_text(encoding="utf-8"))
    selection = json.loads(SELECTION.read_text(encoding="utf-8"))
    pairs = json.loads(PAIRS.read_text(encoding="utf-8"))
    assert pins["schema"] == "a17-var01-prospective-source-pins/v1"
    assert selection["decision"] == "ELIGIBLE_FOR_PROSPECTIVE_CONTRACT_ONLY"
    assert len(pairs) == pins["accepted_source_pair_count"] == selection["source_disk_git_pairs"] == 41
    assert len(pins["required_local_sources"]) == 12
    assert len(pins["mandatory_originals"]) == selection["mandatory_original_count"] == 61
    assert pins["accepted_source_pairs"]["sha256"] == PINNED_PAIRS_SHA
    assert pins["selection_receipt"]["sha256"] == PINNED_SELECTION_SHA
    assert pins["required_local_sources"] == selection["required_local_sources"]
    assert pins["mandatory_originals"] == selection["mandatory_originals"]
    exact(CONVERTER_NEGATIVE, CONVERTER_NEGATIVE_PIN)
    exact(INSTALLED_EXE, INSTALLED_EXE_PIN)
    exact(PYTHON_RUNTIME, PYTHON_RUNTIME_PIN)
    seen = set()
    for row in pairs:
        relative = Path(row["path"])
        assert not relative.is_absolute() and ".." not in relative.parts
        target = (REPO / relative).resolve(strict=True)
        assert target.is_relative_to(REPO.resolve()) and row["path"] not in seen
        seen.add(row["path"])
        exact(target, row["disk"])
    git_batch(pairs, selection["base"])
    for row in pins["required_local_sources"] + pins["mandatory_originals"]:
        target = Path(row["path"])
        exact(target, row)
        if "original_mode" in row:
            st = target.stat()
            assert st.st_mode == row["original_mode"]
            assert getattr(st, "st_file_attributes", None) == row["original_attributes"]
    historical = {}
    for key in ("catalog_local_501", "catalog_git_501"):
        row = pins[key]
        path = Path(row["path"])
        exact(path, row)
        historical[key] = strict_catalog(path)
    local = historical["catalog_local_501"]
    remote = historical["catalog_git_501"]
    assert typed_equal(local, remote)
    assert len(local["entries"]) == 501
    current = strict_catalog(PARENT_CATALOG)
    assert type(current) is dict and list(current) == list(local)
    assert type(current["as_of"]) is str
    for key in local:
        if key not in ("as_of", "entries"):
            assert typed_equal(current[key], local[key]), key
    assert type(current["entries"]) is list and len(current["entries"]) >= 501
    assert all(typed_equal(x, y) for x, y in zip(current["entries"][:501], local["entries"], strict=True))
    assert len({row["publication_id"] for row in current["entries"]}) == len(current["entries"])
    return {
        "schema": "a17-var01-source-gate/v1", "passed": True,
        "accepted_disk_git_pairs": 41, "required_local_sources": 12,
        "mandatory_originals": 61, "catalog_prefix_entries": 501,
        "converter_negative_originals": 1,
        "installed_executables": 2,
        "catalog_current_entries": len(current["entries"]),
        "git_audit": "read-only selected-base ls-tree path/OID binding and batched cat-file over 41 pinned blobs",
    }


if __name__ == "__main__":
    print(json.dumps(verify(), sort_keys=True))
