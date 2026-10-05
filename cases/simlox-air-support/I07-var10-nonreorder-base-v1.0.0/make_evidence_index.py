"""Pin excluded I07.var10 v1.0.0 diagnostic source and immutable raw run."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def entry(path: Path) -> dict:
    raw = path.read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> None:
    contract = load(HERE / "contract.json")
    run = HERE / "runs" / contract["run_id"]
    closure = load(run / "closure.json")
    outcome = load(run / "outcome.json")
    assert closure["run_id"] == contract["run_id"] and len(closure["raw"]) == 22
    assert closure["error"] == outcome["error"] == "change unreviewed converter diagnostic"
    assert outcome["converter_summaries"] == {"control": [0, 1, 0], "change": [0, 2, 0]}
    assert outcome["warning_codes"] == {"control": ["108"], "change": ["108", "172"]}
    assert entry(run / "invocation.json")["sha256"] == closure["invocation_sha256"]
    assert closure["source_hashes_before"] == closure["source_hashes_after"]
    for name, seal in closure["raw"].items():
        assert entry(run / name) == seal, name
    names = sorted(p.relative_to(HERE).as_posix() for p in HERE.rglob("*")
                   if p.is_file() and "runs" not in p.relative_to(HERE).parts
                   and "__pycache__" not in p.relative_to(HERE).parts
                   and p.name != "evidence-index.json")
    required = {".gitattributes", ".gitignore", "README.md", "build.py", "check_roundtrip.py",
                "contract.json", "control-input.json", "change-input.json", "run_native_ssh.ps1",
                "review/preflight-2026-10-05.md", "make_evidence_index.py"}
    assert required <= set(names)
    output = {"schema": "simlox-i07-var10-diagnostic-index/v1", "case_id": "I07",
              "variant_id": "I07.var10", "version": "1.0.0",
              "publication_state": "excluded_diagnostic",
              "reason": "Child native converter adds warning #172; frozen sole-#108 gate stopped before child selected report export.",
              "source": {name: entry(HERE / name) for name in names},
              "run": {"run_id": run.name, "local_directory": str(run),
                      "invocation": entry(run / "invocation.json"),
                      "closure": entry(run / "closure.json"), "raw": closure["raw"]},
              "raw_files_total": 22, "limits": contract["limits"]}
    target = HERE / "evidence-index.json"
    target.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"index_sha256": entry(target)["sha256"], "raw_files": 22}, indent=2))


if __name__ == "__main__":
    main()
