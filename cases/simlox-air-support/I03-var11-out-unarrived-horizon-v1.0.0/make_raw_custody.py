"""Read-only by default: exact original-path custody for 144 prior + 25 child files."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
RUN = HERE / "runs/i03-var11-out-unarrived-v100-ssh-20261008-01"
MAP = HERE / "raw-custody-map.json"


def pin(path: Path) -> dict:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def candidate() -> dict:
    contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
    prior = contract["source_lineage"]["original_raw"]
    assert len(prior) == 144
    rows = []
    for item in prior:
        path = Path(item["original_path"])
        assert pin(path) == {key: item[key] for key in ("bytes", "sha256")}
        rows.append({"classification": item["classification"], "path": str(path), **pin(path)})
    assert sum(r["classification"] == "accepted_or_required_context" for r in rows) == 118
    assert sum(r["classification"] == "excluded_failed_v100_witness" for r in rows) == 26
    closure = json.loads((RUN / "closure.json").read_text(encoding="utf-8-sig"))
    assert len(closure["raw"]) == 23
    names = sorted(p.name for p in RUN.iterdir() if p.is_file())
    assert len(names) == 25 and set(names) == set(closure["raw"]) | {"invocation.json", "closure.json"}
    for name in names:
        path = RUN / name
        seal = pin(path)
        if name in closure["raw"]:
            assert seal == closure["raw"][name]
        rows.append({"classification": "new_child_original_run", "path": str(path), **seal})
    assert len({r["path"] for r in rows}) == len(rows) == 169
    return {"schema": "i03-var11-original-raw-custody/v1", "run_id": contract["run_id"],
            "accepted_context": 118, "excluded_failed_witness": 26,
            "new_child_raw": 23, "new_child_invocation_and_closure": 2,
            "records": rows, "original_paths_mandatory": True}


def main() -> None:
    assert sys.argv[1:] in ([], ["--write"])
    doc = candidate()
    raw = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode()
    if sys.argv[1:] == ["--write"]:
        assert not MAP.exists(), "preserve existing raw custody map"
        MAP.write_bytes(raw)
    else:
        assert MAP.is_file() and MAP.read_bytes() == raw
    print(json.dumps({"schema": "i03-var11-raw-custody-check/v1", "passed": True,
                      "records": len(doc["records"]), "native_started": False}, separators=(",", ":")))


if __name__ == "__main__":
    main()
