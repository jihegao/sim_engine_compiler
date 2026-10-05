"""Pin E15.var10 warning/report extension and its excluded diagnostic parent."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OLD_CASE = HERE.parent / "E15-var10-rosiz-upper-bound-v1.0.0"


def pin(path: Path) -> dict:
    raw = path.read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> None:
    contract = load(HERE / "contract.json")
    run = HERE / "runs" / contract["run_id"]
    closure = load(run / "closure.json")
    old_index = load(OLD_CASE / "evidence-index.json")
    old = OLD_CASE / "runs" / old_index["run"]["run_id"]
    old_closure = load(old / "closure.json")
    assert old_index["publication_state"] == "excluded_diagnostic"
    assert pin(OLD_CASE / "evidence-index.json")["sha256"] == contract["diagnostic_parent"]["evidence_index_sha256"]
    assert pin(old / "closure.json")["sha256"] == contract["diagnostic_parent"]["closure_sha256"]
    assert old_closure["error"] == "expected converter error absent" and len(old_closure["raw"]) == 11
    for name, expected in old_closure["raw"].items():
        assert pin(old / name) == expected == old_index["run"]["raw"][name], name
    assert closure["run_id"] == run.name and closure["error"] is None
    assert closure["parent_closure_sha256"] == pin(old / "closure.json")["sha256"]
    assert closure["source_hashes_before"] == closure["source_hashes_after"]
    assert pin(run / "invocation.json")["sha256"] == closure["invocation_sha256"]
    assert len(closure["raw"]) == 4
    for name, expected in closure["raw"].items():
        assert pin(run / name) == expected, name
    author = load(HERE / "review/author-validation-2026-10-05.json")
    independent = load(HERE / "review/independent-verdict.json")
    assert author["passed"] and author["checks"] == author["checks_passed"] == 200
    assert independent["decision"] == "GO_BOUNDED_WARNING_AND_REPORT_DIAGNOSTIC"
    assert independent["passed"] and independent["checks_passed"] == independent["checks_total"] == 723
    assert author["report_closure_sha256"] == independent["new_closure_sha256"] == pin(run / "closure.json")["sha256"]
    names = sorted(path.relative_to(HERE).as_posix() for path in HERE.rglob("*")
                   if path.is_file() and "runs" not in path.relative_to(HERE).parts
                   and "__pycache__" not in path.relative_to(HERE).parts
                   and path.name != "evidence-index.json")
    required = {".gitattributes", ".gitignore", "README.md", "contract.json",
                "run_report_ssh.ps1", "validate.py", "make_evidence_index.py",
                "cli-scope-signoff-2026-10-05.md", "review/author-validation-2026-10-05.json",
                "review/independent_replay.py", "review/independent-verdict.json",
                "review/preflight-2026-10-05.md", "review/postrun-2026-10-05.md",
                "review/static-preflight-2026-10-05.md", "review/static-postrun-2026-10-05.md"}
    assert required <= set(names), sorted(required - set(names))
    index = {"schema": "simlox-e15-var10-warning-report-evidence-index/v1",
             "case_id": "E15", "variant_id": "E15.var10", "version": "1.0.1",
             "publication_state": "not_published", "source": {name: pin(HERE / name) for name in names},
             "diagnostic_parent": {"package": OLD_CASE.name, "evidence_index": pin(OLD_CASE / "evidence-index.json"),
                                   "closure": pin(old / "closure.json"), "raw_files_total": 11,
                                   "publication_state": "excluded_diagnostic"},
             "run": {"run_id": run.name, "local_directory": str(run),
                     "invocation": pin(run / "invocation.json"), "closure": pin(run / "closure.json"),
                     "raw": closure["raw"]}, "raw_files_total": 4, "limits": contract["limits"]}
    path = HERE / "evidence-index.json"
    path.write_text(json.dumps(index, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({"index_sha256": pin(path)["sha256"], "old_raw": 11, "new_raw": 4}))


if __name__ == "__main__":
    main()
