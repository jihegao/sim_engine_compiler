"""Pin both immutable I07.var10 runs and all published extension source bytes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "I07-var10-nonreorder-base-v1.0.0"


def entry(path: Path) -> dict:
    raw = path.read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> None:
    contract = load(HERE / "contract.json")
    run = HERE / "runs" / contract["run_id"]
    closure = load(run / "closure.json")
    old_index = load(PARENT / "evidence-index.json")
    old = PARENT / "runs" / old_index["run"]["run_id"]
    old_closure = load(old / "closure.json")
    assert old_index["publication_state"] == "excluded_diagnostic"
    assert entry(PARENT / "evidence-index.json")["sha256"] == contract["diagnostic_parent"]["evidence_index_sha256"]
    assert entry(old / "closure.json")["sha256"] == contract["diagnostic_parent"]["closure_sha256"]
    assert old_closure["error"] == "change unreviewed converter diagnostic"
    assert len(old_closure["raw"]) == 22
    for name, pin in old_closure["raw"].items():
        assert entry(old / name) == pin == old_index["run"]["raw"][name], name
    assert closure["run_id"] == run.name and closure["error"] is None
    assert closure["source_hashes_before"] == closure["source_hashes_after"]
    assert closure["parent_closure_sha256"] == entry(old / "closure.json")["sha256"]
    assert entry(run / "invocation.json")["sha256"] == closure["invocation_sha256"]
    assert len(closure["raw"]) == 4
    for name, pin in closure["raw"].items():
        assert entry(run / name) == pin, name
    author = load(HERE / "review/author-validation-2026-10-05.json")
    independent = load(HERE / "review/independent-verdict.json")
    assert author["passed"] and author["checks"] == author["checks_passed"] == 155
    assert independent["decision"] == "GO_BOUNDED" and independent["passed"] == independent["total"] == 171
    assert author["report_closure_sha256"] == independent["report_extension_closure_sha256"] == entry(run / "closure.json")["sha256"]
    names = sorted(p.relative_to(HERE).as_posix() for p in HERE.rglob("*")
                   if p.is_file() and "runs" not in p.relative_to(HERE).parts
                   and "__pycache__" not in p.relative_to(HERE).parts
                   and p.name != "evidence-index.json")
    required = {".gitattributes", ".gitignore", "README.md", "contract.json", "run_report_ssh.ps1",
                "validate.py", "make_evidence_index.py", "cli-scope-signoff-2026-10-05.md",
                "review/preflight-2026-10-05.md", "review/static-postrun-2026-10-05.md",
                "review/author-validation-initial-failure-2026-10-05.json",
                "review/author-validation-2026-10-05.json", "review/independent_replay.py",
                "review/independent-verdict.json"}
    assert required <= set(names), sorted(required - set(names))
    output = {"schema": "simlox-i07-var10-report-extension-evidence-index/v1",
              "case_id": "I07", "variant_id": "I07.var10", "version": "1.0.1",
              "publication_state": "not_published",
              "source": {name: entry(HERE / name) for name in names},
              "diagnostic_parent": {"package": PARENT.name,
                                    "evidence_index": entry(PARENT / "evidence-index.json"),
                                    "closure": entry(old / "closure.json"),
                                    "raw_files_total": 22,
                                    "publication_state": "excluded_diagnostic"},
              "run": {"run_id": run.name, "local_directory": str(run),
                      "invocation": entry(run / "invocation.json"),
                      "closure": entry(run / "closure.json"), "raw": closure["raw"]},
              "raw_files_total": 4, "limits": contract["limits"]}
    target = HERE / "evidence-index.json"
    target.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"index_sha256": entry(target)["sha256"], "old_raw": 22, "new_raw": 4}, indent=2))


if __name__ == "__main__":
    main()
