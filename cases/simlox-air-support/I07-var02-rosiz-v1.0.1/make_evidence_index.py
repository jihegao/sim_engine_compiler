"""Pin source bytes and the sealed local raw run for I07.var02."""
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
    assert closure["run_id"] == contract["run_id"] and closure["error"] is None
    assert entry(run / "invocation.json")["sha256"] == closure["invocation_sha256"]
    assert closure["source_hashes_before"] == closure["source_hashes_after"]
    assert len(closure["raw"]) == 22
    for name, seal in closure["raw"].items():
        assert entry(run / name) == seal, name

    source_names = sorted(p.relative_to(HERE).as_posix() for p in HERE.rglob("*")
                          if p.is_file() and "runs" not in p.relative_to(HERE).parts
                          and "__pycache__" not in p.relative_to(HERE).parts
                          and p.name != "evidence-index.json")
    required = {
        ".gitattributes", ".gitignore", "build.py", "contract.json", "run_native_ssh.ps1",
        "control-input.json", "change-input.json", "validate.py", "make_evidence_index.py",
        "review/preflight-2026-10-05.md", "review/author-validation-2026-10-05.json",
        "review/independent-readonly-2026-10-05.json", "cli-scope-signoff-2026-10-05.md", "README.md",
    }
    assert required <= set(source_names), sorted(required - set(source_names))
    verdict = load(HERE / "review/independent-readonly-2026-10-05.json")
    assert verdict["passed"] is True
    author = load(HERE / "review/author-validation-2026-10-05.json")
    assert author["passed"] is True and author["closure_sha256"] == entry(run / "closure.json")["sha256"]
    result = {
        "schema": "simlox-i07-rosiz-evidence-index/v1",
        "case_id": "I07", "variant_id": "I07.var02", "version": "1.0.1",
        "publication_state": "not_published",
        "source": {name: entry(HERE / name) for name in source_names},
        "run": {"run_id": contract["run_id"], "local_directory": str(run),
                "invocation": entry(run / "invocation.json"),
                "closure": entry(run / "closure.json"), "raw": closure["raw"]},
        "raw_files_total": len(closure["raw"]),
        "prerequisites": contract["prerequisites"],
        "manual_sha256": contract["source"]["manual_pdf_sha256"],
        "dictionary_sha256": contract["source"]["dictionary_sha256"],
        "limits": contract["limits"],
    }
    destination = HERE / "evidence-index.json"
    destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"closure_sha256": result["run"]["closure"]["sha256"],
                      "raw_files": len(closure["raw"]),
                      "index_sha256": entry(destination)["sha256"]}, indent=2))


if __name__ == "__main__":
    main()
