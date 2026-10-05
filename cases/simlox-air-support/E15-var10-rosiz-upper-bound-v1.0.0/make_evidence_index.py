"""Pin the excluded E15.var10 strict-error diagnostic and every local raw byte."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def pin(path: Path) -> dict:
    raw = path.read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> None:
    contract = load(HERE / "contract.json")
    run = HERE / "runs" / contract["run_id"]
    closure, outcome = load(run / "closure.json"), load(run / "outcome.json")
    independent = load(HERE / "review/independent-verdict.json")
    assert closure["run_id"] == run.name and closure["expected_negative"] is False
    assert closure["error"] == outcome["error"] == "expected converter error absent"
    assert outcome["converter_summary"] == [0, 2, 0]
    assert pin(run / "invocation.json")["sha256"] == closure["invocation_sha256"]
    assert closure["source_hashes_before"] == closure["source_hashes_after"]
    assert len(closure["raw"]) == 11
    for name, expected in closure["raw"].items():
        assert pin(run / name) == expected, name
    assert independent["decision"] == "NO_GO_FROZEN_NEGATIVE_GATE" and independent["checks_passed"] == independent["checks_total"] == 69
    assert independent["closure_sha256"] == pin(run / "closure.json")["sha256"]
    names = sorted(path.relative_to(HERE).as_posix() for path in HERE.rglob("*")
                   if path.is_file() and "runs" not in path.relative_to(HERE).parts
                   and "__pycache__" not in path.relative_to(HERE).parts
                   and path.name != "evidence-index.json")
    required = {".gitattributes", ".gitignore", "README.md", "build.py", "check_roundtrip.py",
                "contract.json", "native-input.json", "run_native_ssh.ps1", "make_evidence_index.py",
                "review/preflight-2026-10-05.md", "review/static-preflight-2026-10-05.md",
                "review/static-postrun-2026-10-05.md", "review/postrun-2026-10-05.md",
                "review/independent_replay.py", "review/independent-verdict.json"}
    assert required <= set(names), sorted(required - set(names))
    index = {"schema": "simlox-e15-var10-excluded-diagnostic-index/v1", "case_id": "E15",
             "variant_id": "E15.var10", "version": "1.0.0", "publication_state": "excluded_diagnostic",
             "reason": "Frozen contract required converter error and no valid SXO; native warning #168 allowed simulation.",
             "source": {name: pin(HERE / name) for name in names},
             "run": {"run_id": run.name, "local_directory": str(run),
                     "invocation": pin(run / "invocation.json"), "closure": pin(run / "closure.json"),
                     "raw": closure["raw"]}, "raw_files_total": len(closure["raw"]),
             "limits": contract["limits"]}
    path = HERE / "evidence-index.json"
    path.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"index_sha256": pin(path)["sha256"], "raw_files": len(closure["raw"])}))


if __name__ == "__main__":
    main()
