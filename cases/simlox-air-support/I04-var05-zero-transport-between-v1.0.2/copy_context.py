"""Own small recovery records while retaining mandatory original failed evidence."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from model_common import read

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
ROOT = HERE / "preserved-context"
MAP = HERE / "context-custody.json"
CONTRACT = HERE / "prospective-contract.json"
OLD = REPO / "cases/simlox-air-support/I04-var05-zero-transport-between-v1.0.0"
CONTRACT_PIN = {"bytes": 922508, "sha256": "2353d18f907803c9023089e70202e7381cad266a0b8c7795bf98586ee067f292"}
CATALOGS = {
    "catalog-local-497.json.bytes": (OLD / "preserved-context/catalog-local-497.json.bytes", 534641,
                                     "e4c3966bb85829ffafadf9331ef6a719431fbab58c8203bc017d188884cfc696"),
    "catalog-git-497.json.bytes": (OLD / "preserved-context/catalog-git-497.json.bytes", 529992,
                                   "ab9bd439b967d15965a54482b783070408d92d9a17a4963b35447b9a3c631dd3"),
}


def seal(path: Path) -> dict:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def write_once(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as stream:
        stream.write(data)


def specification() -> tuple[list[dict], set[str]]:
    assert seal(CONTRACT) == CONTRACT_PIN
    recovery = read(CONTRACT)["recovery"]
    support = recovery["frozen_v100_supporting_originals"]
    raw = recovery["frozen_v100_failure_originals"] + recovery["frozen_v100_preflight_originals"]
    assert len(support) == 131 and len(raw) == 52
    mandatory = {row["path"].casefold() for row in raw}
    large = [row for row in support if Path(row["path"]).name == "tree-stdout.bin" and row["bytes"] > 1_000_000]
    assert len(large) == 1 and large[0]["bytes"] == 1903336
    mandatory.add(large[0]["path"].casefold())
    assert len(mandatory) == 53
    return support, mandatory


def verify() -> dict:
    mapping = read(MAP)
    assert set(mapping) == {"schema", "records", "supporting_records", "owned_copy_records",
                            "mandatory_host_original_records", "originals_optional_only_when_owned_copy_exists",
                            "catalog_archives"}
    assert mapping["schema"] == "i04-var05-v101-context-custody/v1"
    assert mapping["originals_optional_only_when_owned_copy_exists"] is True
    assert (mapping["supporting_records"], mapping["owned_copy_records"],
            mapping["mandatory_host_original_records"]) == (131, 78, 53)
    support, mandatory = specification()
    assert len(mapping["records"]) == len(support)
    copy_index = 0
    for index, (row, source) in enumerate(zip(mapping["records"], support)):
        assert set(row) == {"index", "original_path", "bytes", "sha256", "disposition", "owned_copy"}
        assert type(row["index"]) is int and row["index"] == index
        assert row["original_path"] == source["path"]
        assert (row["bytes"], row["sha256"]) == (source["bytes"], source["sha256"])
        expected = {"bytes": source["bytes"], "sha256": source["sha256"]}
        original = Path(row["original_path"])
        if row["original_path"].casefold() in mandatory:
            assert row["disposition"] == "mandatory_host_original_no_copy" and row["owned_copy"] is None
            assert original.is_file() and seal(original) == expected
        else:
            assert row["disposition"] == "owned_copy_original_if_present"
            assert row["owned_copy"] == f"preserved-context/context-{copy_index:03d}.bytes"
            assert seal(HERE / row["owned_copy"]) == expected
            if original.exists():
                assert seal(original) == expected
            copy_index += 1
    assert copy_index == 78
    assert set(mapping["catalog_archives"]) == set(CATALOGS)
    for name, (source, size, digest) in CATALOGS.items():
        row = mapping["catalog_archives"][name]
        assert row == {"owned_copy": f"preserved-context/{name}",
                       "original_path": str(source), "bytes": size, "sha256": digest}
        assert seal(HERE / row["owned_copy"]) == {"bytes": size, "sha256": digest}
        if source.exists():
            assert seal(source) == {"bytes": size, "sha256": digest}
    return {"schema": mapping["schema"], "records": 131,
            "owned_copies": 78, "mandatory_host_originals": 53}


def create() -> dict:
    assert not MAP.exists()
    support, mandatory = specification()
    rows = []
    copy_index = 0
    for index, source in enumerate(support):
        original = Path(source["path"])
        expected = {"bytes": source["bytes"], "sha256": source["sha256"]}
        assert original.is_file() and seal(original) == expected
        if source["path"].casefold() in mandatory:
            disposition, owned = "mandatory_host_original_no_copy", None
        else:
            disposition = "owned_copy_original_if_present"
            owned = f"preserved-context/context-{copy_index:03d}.bytes"
            write_once(HERE / owned, original.read_bytes())
            copy_index += 1
        rows.append({"index": index, "original_path": source["path"],
                     **expected, "disposition": disposition, "owned_copy": owned})
    assert copy_index == 78
    catalogs = {}
    for name, (source, size, digest) in CATALOGS.items():
        assert seal(source) == {"bytes": size, "sha256": digest}
        write_once(ROOT / name, source.read_bytes())
        catalogs[name] = {"owned_copy": f"preserved-context/{name}",
                          "original_path": str(source), "bytes": size, "sha256": digest}
    result = {"schema": "i04-var05-v101-context-custody/v1", "records": rows,
              "supporting_records": 131, "owned_copy_records": 78,
              "mandatory_host_original_records": 53,
              "originals_optional_only_when_owned_copy_exists": True,
              "catalog_archives": catalogs}
    write_once(MAP, (json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode())
    return verify()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    print(json.dumps(create() if args.write else verify(), sort_keys=True))
