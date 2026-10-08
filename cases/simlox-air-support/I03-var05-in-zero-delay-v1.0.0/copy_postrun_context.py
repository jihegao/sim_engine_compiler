"""Own small original root/reviewer phase proofs; default verifies only."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
DEST = HERE / "preserved-postrun-context"
MAP = HERE / "postrun-context-custody.json"

# These names identify the closed phase set captured before publication. Runs,
# installed files, accepted raw and native transport are audited separately.
DIRS = (
    "tmp/i03-var05-independent-contract-v3-proof-20261008-01",
    "tmp/i03-var05-independent-contract-v4-proof-20261008-01",
    "tmp/i03-var05-root-source-freeze-20261008-01",
    "tmp/i03-var05-root-independent-pure-capture-20261008-01",
    "tmp/i03-var05-independent-pure-preflight-proof-20261008-01",
    "tmp/i03-var05-root-ssh-preflight-20261008-01",
    "tmp/i03-var05-independent-actual-preflight-proof-20261008-01",
    "tmp/i03-var05-root-owner-proof-20261008-01",
    "tmp/i03-var05-root-live-refs-20261008-01",
    "tmp/i03-var05-root-native-dispatch-20261008-01",
    "tmp/i03-var05-independent-postrun-capture-20261008-01",
    "tmp/i03-var05-root-postrun-audit-proof-20261008-01",
    "tmp/i03-var05-root-catalog-regression-20261008-01",
    "cases/simlox-air-support/I03-var05-in-zero-delay-v1.0.0/test-output/pure-proof-20261008T012123561162Z-8dc97dc5",
)
SINGLES = (
    "tmp/i03-var05-author-freeze-handoff-20261008.py",
    "tmp/i03-var05-author-freeze-ready-20261008.json",
    "tmp/i03-var05-root-source-freeze-20261008.py",
    "tmp/i03-var05-root-independent-pure-capture-20261008.py",
    "tmp/i03-var05-independent-pure-preflight-proof-20261008.py",
    "tmp/i03-var05-independent-pure-preflight-audit-draft-v1-20261008.py",
    "tmp/i03-var05-independent-pure-preflight-audit-20261008.py",
    "tmp/i03-var05-independent-pure-preflight-go-20261008.md",
    "tmp/i03-var05-root-ssh-preflight-20261008.py",
    "tmp/i03-var05-independent-actual-preflight-audit-20261008.py",
    "tmp/i03-var05-independent-prelaunch-decision-20261008.py",
    "tmp/i03-var05-independent-prelaunch-go-20261008.md",
    "tmp/i03-var05-root-owner-capture-20261008.py",
    "tmp/i03-var05-root-live-refs-20261008.py",
    "tmp/i03-var05-root-app-ownership-20261008.json",
    "tmp/i03-var05-root-preflight-app-ownership-20261008.json",
    "tmp/i03-var05-root-launch-app-ownership-20261008.json",
    "tmp/i03-var05-root-native-dispatch-20261008.py",
    "tmp/i03-var05-independent-postrun-capture-20261008.py",
    "tmp/i03-var05-root-postrun-seal-audit-20261008.py",
    "tmp/i03-var05-root-postrun-seal-audit-v2-20261008.py",
    "tmp/i03-var05-root-postrun-audit-repair-capture-20261008.py",
    "tmp/i03-var05-root-postrun-seal-audit-20261008.json",
    "tmp/i03-var05-root-ref-read-diagnostic-20261008.json",
    "tmp/i03-var05-root-catalog-append-regression-20261008.py",
    "tmp/i03-var05-reviewer-turn-failure-20261008.json",
)


def pin(data: bytes) -> dict:
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def sources() -> list[Path]:
    files = [REPO / name for name in SINGLES]
    for name in DIRS:
        directory = REPO / name
        assert directory.is_dir(), name
        files.extend(sorted(path for path in directory.iterdir() if path.is_file()))
    assert len(files) == len({str(p).lower() for p in files})
    assert all(p.is_file() for p in files)
    return files


def verify() -> dict:
    rows = json.loads(MAP.read_bytes())["records"]
    assert rows and len(rows) == len({row["owned_copy"] for row in rows})
    for row in rows:
        owned = HERE / row["owned_copy"]
        wanted = {key: row[key] for key in ("bytes", "sha256")}
        assert pin(owned.read_bytes()) == wanted
        original = Path(row["original_path"])
        if original.exists():
            assert pin(original.read_bytes()) == wanted
    return {"schema": "i03-var05-postrun-context-check/v1", "records": len(rows)}


def write() -> dict:
    assert not MAP.exists() and not DEST.exists()
    originals = sources()
    records = []
    for index, original in enumerate(originals, 1):
        data = original.read_bytes()
        records.append({"original_path": str(original.resolve(strict=True)),
                        "owned_copy": f"preserved-postrun-context/c{index:03d}.bytes",
                        "original_if_present_must_match": True, **pin(data)})
    DEST.mkdir()
    for row, original in zip(records, originals, strict=True):
        target = HERE / row["owned_copy"]
        target.write_bytes(original.read_bytes())
        assert pin(target.read_bytes()) == {key: row[key] for key in ("bytes", "sha256")}
    result = {"schema": "i03-var05-postrun-context-custody/v1", "records": records,
              "original_tmp_paths_optional_after_publication": True,
              "accepted_and_child_original_raw_remain_mandatory": True,
              "native_transport_originals_separately_mandatory": True,
              "limitations": "Historical tool-only diagnostics do not acquire original stdout/stderr byte identity through a copy."}
    MAP.write_bytes((json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))
    verify()
    return {"schema": result["schema"], "records": len(records), "map": pin(MAP.read_bytes())}


if __name__ == "__main__":
    assert sys.argv[1:] in ([], ["--write"])
    print(json.dumps(write() if sys.argv[1:] else verify(), sort_keys=True))
