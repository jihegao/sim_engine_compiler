"""Pin the source-bound I07.var05 mapping and original accepted I07.var02 run."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "I07-var02-rosiz-v1.0.1"


def entry(path: Path) -> dict:
    raw = path.read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> None:
    contract = load(HERE / "contract.json")
    parent = load(PARENT / "evidence-index.json")
    run = PARENT / "runs" / contract["accepted_parent"]["run_id"]
    assert entry(PARENT / "evidence-index.json")["sha256"] == contract["accepted_parent"]["evidence_index_sha256"]
    assert entry(run / "closure.json") == parent["run"]["closure"]
    for name, seal in parent["run"]["raw"].items():
        assert entry(run / name) == seal, name
    names = sorted(p.relative_to(HERE).as_posix() for p in HERE.rglob("*")
                   if p.is_file() and "__pycache__" not in p.relative_to(HERE).parts
                   and p.name != "evidence-index.json")
    required = {"README.md", "cli-scope-signoff-2026-10-05.md", "contract.json",
                "validate.py", "make_evidence_index.py", "review/preflight-2026-10-05.md",
                "review/author-diagnostic-first-pass-2026-10-05.json",
                "review/author-validation-2026-10-05.json",
                "review/independent_replay.py", "review/independent-verdict.json"}
    assert required <= set(names), sorted(required - set(names))
    author = load(HERE / "review/author-validation-2026-10-05.json")
    independent = load(HERE / "review/independent-verdict.json")
    assert author["passed"] is True and author["parent_closure_sha256"] == parent["run"]["closure"]["sha256"]
    assert independent["decision"] == "GO_BOUNDED" and independent["failures"] == []
    assert independent["accepted_closure_sha256"] == parent["run"]["closure"]["sha256"]
    output = {"schema": "simlox-i07-var05-source-bound-evidence-index/v1",
              "case_id": "I07", "variant_id": "I07.var05", "version": "1.0.0",
              "publication_state": "not_published", "native_run_reused": True,
              "source": {name: entry(HERE / name) for name in names},
              "accepted_parent": {"package": contract["accepted_parent"]["package"],
                                  "evidence_index": entry(PARENT / "evidence-index.json"),
                                  "run_id": run.name, "closure": entry(run / "closure.json"),
                                  "original_raw": parent["run"]["raw"]},
              "raw_files_reused": len(parent["run"]["raw"]),
              "observation_window_hours": [5, 10], "limits": contract["limits"]}
    destination = HERE / "evidence-index.json"
    destination.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"source_files": len(names), "original_raw": len(parent["run"]["raw"]),
                      "index_sha256": entry(destination)["sha256"]}, indent=2))


if __name__ == "__main__":
    main()
