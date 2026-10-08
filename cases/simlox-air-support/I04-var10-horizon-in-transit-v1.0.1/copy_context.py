"""Own exact inert copies of excluded v100 construction and contract history."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from model_common import encode, pin, read, verify_expected

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
MAP = HERE / "context-custody.json"
ARCHIVE = HERE / "preserved-context"
OLD_INDEX = REPO / "tmp/i04-var10-v100-excluded-construction-inventory-20261008.json"
OLD_INDEX_PIN = {"bytes": 6480, "sha256": "410514cbb51bc0634d8e74eb14f131a528eab58469d4c3ec04c8b822bc99a780"}
EXTRA = (
    ("tmp/i04-var10-root-preserved-v100-20261008.json", 5990, "34b547424b8ba5857a2c5789138320ebdb45210b9801ca3eb27bdfb2755dad60"),
    ("tmp/i04-var10-independent-prelaunch-static-no-go-v100-20261008.md", 2704, "1dc6fb1df0bd6180602941a1a0a5723fca534e985ce3b23e242de8f035503372"),
    ("tmp/i04-var10-independent-contract-go-v100-20261008.md", 5552, "371d534508f881346c34a9af2ad3e79171531a3be3d4757f1ce3902807b53887"),
    ("tmp/i04-var10-independent-contract-go-v101-20261008.md", 5689, "e3216eed06f7cb21c1bf65c613069f4a33e0148f8915439c9d65f3359cdc630b"),
    ("tmp/i04-var10-build-prospective-v101-v2-20261008.py", 29359, "9d4846c87df8538da792b43839ba183219b847f38b69c4ae1fb93cb635c069b8"),
    ("tmp/i04-var09-root-review-proofs-v100-20261008/i04-var10-prospective-v101-generation-20261008T125706458474Z-e8bf1bc0/receipt.json", 1363, "7bb69f4da050f7b23f539447d84d2bc1bc658e30b105121b92fca627b63e1c03"),
)
DEVELOPMENT = {
    "source-gate-v1-cwd-dependent-accepted-refs.py.bytes": {"bytes": 10527, "sha256": "a493ef213d81dfd11d413ec46c355a1dcf8725904c3d56e23e9ca908d4302295"},
    "preflight-native-path-array-static-finding.md": {"bytes": 1169, "sha256": "65810e4c616922ae5875c4737f70e09a9a775a982b047e9f33a086ea1ca07413"},
    "test-converter-v1-reparse-extraction-failure.ps1.bytes": {"bytes": 6738, "sha256": "b27ce6af98fae0f9709d979ab0a096a86030d1457c8c3b861243d417a7e95f86"},
    "test-converter-v1-reparse-extraction-failure.md": {"bytes": 769, "sha256": "d4bf94e8ea158c4786cbf34a4b6c5d154b4d70c0c212dd7db7b97e987b78f53b"},
    "test-converter-v2-junction-removal-failure.ps1.bytes": {"bytes": 6739, "sha256": "d6d7260ebea881ee5a1a8794b96ebdd3253d3dd110abd76791c511e83367d015"},
    "test-converter-v2-junction-removal-failure.md": {"bytes": 1513, "sha256": "3d001331a745a372b14a35b87be4fd811c26beabab8b802adff4f242a1c8e8bb"},
    "source-gate-v2-development-count-drift.py.bytes": {"bytes": 12789, "sha256": "b5f98d128a9fa7b2d1aa4007631392e7bd3551814a36eb024a7532929a1021ab"},
    "manifest-v1-development-count-drift.py.bytes": {"bytes": 9602, "sha256": "f778239523963ab7890d1d40a216b8b5741c146b3ab2726853f2a059698df8b4"},
    "manifest-v1-development-count-drift.md": {"bytes": 966, "sha256": "1e0729e763323c4d263c1bebd60d20b8b69f8b07319886dbd6f1428eb67755fc"},
}


def rows():
    assert pin(OLD_INDEX) == OLD_INDEX_PIN
    index = read(OLD_INDEX)
    assert index["source_count"] == len(index["source_files"]) == 24
    originals = [(REPO / row["path"], row["bytes"], row["sha256"]) for row in index["source_files"]]
    originals += [(REPO / path, size, sha) for path, size, sha in EXTRA]
    assert len(originals) == 30
    return [{"original_path": str(path), "owned_copy": f"preserved-context/context-{i:03d}.bytes",
             "bytes": size, "sha256": sha, "original_if_present_must_match": True}
            for i, (path, size, sha) in enumerate(originals)]


def verify():
    for name, wanted in DEVELOPMENT.items():
        assert pin(HERE / "preserved-development" / name) == wanted
    document = read(MAP)
    expected = {"schema": "i04-var10-v101-context-custody/v1", "originals_mandatory_on_this_host": True,
                "excluded_v100_owned": 24, "extra_history_owned": 6, "records": rows()}
    assert document == expected
    for row in document["records"]:
        copy = HERE / row["owned_copy"]
        assert pin(copy) == {key: row[key] for key in ("bytes", "sha256")}
        original = Path(row["original_path"])
        assert original.is_file() and original.read_bytes() == copy.read_bytes()
    return {"schema": document["schema"], "copies": 30, "development_records": 9}


def main(write=False):
    document = {"schema": "i04-var10-v101-context-custody/v1",
                "originals_mandatory_on_this_host": True,
                "excluded_v100_owned": 24, "extra_history_owned": 6, "records": rows()}
    if write:
        for row in document["records"]:
            source = Path(row["original_path"])
            assert pin(source) == {key: row[key] for key in ("bytes", "sha256")}
            target = HERE / row["owned_copy"]
            assert not target.exists()
            with target.open("xb") as stream:
                stream.write(source.read_bytes())
    verify_expected(MAP, encode(document), write)
    print(json.dumps({**verify(), "native_calls": 0}, sort_keys=True))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    main(parser.parse_args().write)
