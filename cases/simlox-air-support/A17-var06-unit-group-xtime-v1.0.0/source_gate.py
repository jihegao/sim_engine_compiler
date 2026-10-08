"""Read-only, append-stable source custody for prospective A17.var06."""

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
CONTRACT = HERE / "preserved-design/contract.json"
REPORT = HERE / "preserved-design/oracle-map.json"
LOG_FORMS = HERE / "prospective-log-oracle.bytes"
PARENT_CATALOG = REPO / "cases/simlox-air-support/publication-index-v1.json"
CONVERTER_NEGATIVE = REPO / "cases/simlox-air-support/I04-var05-zero-transport-between-v1.0.0/runs/i04-var05-zero-transport-between-v100-ssh-20261008-01/model-run.log"
CONVERTER_NEGATIVE_PIN = {"bytes": 1122, "sha256": "ca209899bce7e299b49d9a482469efd8c0fee0d9f56673ffb99783cbf689457a"}
INSTALLED_EXE = Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe")
INSTALLED_EXE_PIN = {"bytes": 33196032, "sha256": "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0"}
PYTHON_RUNTIME = Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe")
PYTHON_RUNTIME_PIN = {"bytes": 106448, "sha256": "10d845f50a2af64e3500bb2fcb348b5bc98a75d8ddada63e45ba1da6a1fc79d1"}
PINNED_SOURCE_SHA = "621ef7d779a93d243d04faf3769929ad9695d04d0f66f339b2fc7a56c7e9f049"
PINNED_PAIRS_SHA = "66d9993d8ca7a3113811761b66e087574c3e8ca8c91ca295c0b651b8999ad541"
PINNED_SELECTION_SHA = "04d57600dd94386e2fd929bc3b01e2eab5f5c5cb21f23f130399b46a0dbfa7c2"
PINNED_CONTRACT_SHA = "58c12480998f691b619f305922eace2eb1b4aede71fbb779de77ad0085bb15e7"
PINNED_REPORT_SHA = "e1e713ec003cf0d2cba62e38161cd57c504161b3503b624f63d0e33067a40371"
PINNED_FORMS_SHA = "ae6c8430c26490c16e98f7ea66a0137ea7bcd1e309c1f2ba46a44940a0e7f33e"
PINNED_CHILD_INPUT = {"bytes": 43061, "sha256": "21a88bfe7eb34c42e2f11f541f624c42c3530ffc849af475c6fd31909350d22a"}
PINNED_CHILD_EXPORT_ORACLE = {"bytes": 59625, "sha256": "92c83e28dbdd44be0f89c4355b693bd7df4099a96b577161a7839cf4a4b2213e"}
PRESERVED_DESIGN = {
    "author-child-build-v100.py.bytes": {"bytes": 4761, "sha256": "1648233fdd1625876b1e9a2eb54744de3b71796dc29fdc67522be0ac8873d5ee"},
    "README.md": {"bytes": 3151, "sha256": "529095708ff340d17d9878ed37fb28a84c33e509b9d9a2528673faa61dcab1fc"},
    "independent-contract-go.md": {"bytes": 4139, "sha256": "2f04c6372f937a1d1453ba346940775ca176b533886ecd5dd8d1387e842d3616"},
    "independent-audit-v100-unexecuted.py.bytes": {"bytes": 8969, "sha256": "0b5e65961d3b19dd356107ea8b6f245a5562a03713f5af2023b24d5053cc0fdd"},
    "independent-audit-v101.py.bytes": {"bytes": 8993, "sha256": "e11aed8ca116d0bc6afdd177be0317ac43779e98a91c263974ff4c4606628952"},
    "independent-audit-receipt.json": {"bytes": 1370, "sha256": "f8d76246b13dc684b926927889521c24da51f4e7e3520cac1dd082db5c1ac3f1"},
    "independent-audit-stdout.bin": {"bytes": 111, "sha256": "baf2a04fcd797027ec68b3fd77f03748aac603c9ac68263d51a205267147f13c"},
    "independent-audit-stderr.bin": {"bytes": 0, "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"},
}


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
    assert pins["schema"] == "a17-var06-prospective-source-pins/v100"
    assert selection["decision"] == "ELIGIBLE_FOR_PROSPECTIVE_CONTRACT_ONLY"
    assert len(pairs) == selection["source_disk_git_pairs"] == 59
    assert len(pins["required_local_sources"]) == 12
    assert len(pins["mandatory_originals"]) == selection["mandatory_original_count"] == 66
    assert pins["accepted_source_pairs"]["sha256"] == PINNED_PAIRS_SHA
    assert pins["selection_receipt"]["sha256"] == PINNED_SELECTION_SHA
    assert pins["required_local_sources"] == selection["required_local_sources"]
    assert pins["mandatory_originals"] == selection["mandatory_originals"]
    exact(CONVERTER_NEGATIVE, CONVERTER_NEGATIVE_PIN)
    exact(INSTALLED_EXE, INSTALLED_EXE_PIN)
    exact(PYTHON_RUNTIME, PYTHON_RUNTIME_PIN)
    exact(HERE / "native-input.json", PINNED_CHILD_INPUT)
    exact(HERE / "child-roundtrip-oracle.json", PINNED_CHILD_EXPORT_ORACLE)
    for name, pin in PRESERVED_DESIGN.items():
        exact(HERE / "preserved-design" / name, pin)
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
    for key in ("catalog_local_502", "catalog_git_502"):
        row = pins[key]
        path = Path(row["path"])
        exact(path, row)
        historical[key] = strict_catalog(path)
    local = historical["catalog_local_502"]
    remote = historical["catalog_git_502"]
    assert typed_equal(local, remote)
    assert len(local["entries"]) == 502
    current = strict_catalog(PARENT_CATALOG)
    assert type(current) is dict and list(current) == list(local)
    assert type(current["as_of"]) is str
    for key in local:
        if key not in ("as_of", "entries"):
            assert typed_equal(current[key], local[key]), key
    assert type(current["entries"]) is list and len(current["entries"]) >= 502
    assert all(typed_equal(x, y) for x, y in zip(current["entries"][:502], local["entries"], strict=True))
    assert len({row["publication_id"] for row in current["entries"]}) == len(current["entries"])
    return {
        "schema": "a17-var06-source-gate/v100", "passed": True,
        "accepted_disk_git_pairs": 59, "required_local_sources": 12,
        "mandatory_originals": 66, "catalog_prefix_entries": 502,
        "converter_negative_originals": 1,
        "installed_executables": 2,
        "catalog_current_entries": len(current["entries"]),
        "git_audit": "read-only selected-base ls-tree path/OID binding and batched cat-file over 59 pinned blobs",
    }


if __name__ == "__main__":
    print(json.dumps(verify(), sort_keys=True))
