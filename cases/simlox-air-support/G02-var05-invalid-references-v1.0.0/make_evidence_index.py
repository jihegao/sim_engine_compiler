"""Freeze G02.var05 source and native raw seals after independent review."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "G02-var01-position-modes-v1.0.0"
VARIANTS = ("valid-control", "missing-fmid-mid", "missing-structure-mother")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def record(variant: str) -> dict:
    run_id = f"g02-var05-{variant}-20261002-01"
    run = HERE / "runs" / run_id
    invocation = load(run / "invocation.json")
    closure = load(run / "closure.json")
    steps = load(run / "steps.json")
    assert invocation["run_id"] == closure["run_id"] == run_id
    assert invocation["variant"] == variant
    assert sha(run / "invocation.json") == closure["invocation_sha256"]
    assert closure["source_hashes_before"] == closure["source_hashes_after"]
    source = closure["source_hashes_before"]
    expected = {
        "input": HERE / f"{variant}-input.json",
        "parent": PARENT / "native-input.json",
        "manual": Path("C:/Program Files/Systecon/SIMLOX/UserDoc/SIMLOX.pdf"),
        "dictionary": Path("C:/Program Files/Systecon/SIMLOX/UserDoc/Table relations/DatabaseDictionary_SIMLOX.txt"),
        "contract": HERE / "contract.json", "builder": HERE / "build.py",
        "checker": HERE / "check_roundtrip.py", "runner_script": HERE / "run_native_ssh.ps1",
        "python": Path("C:/Users/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe"),
        "simlox_exe": Path("C:/Program Files/Systecon/SIMLOX/Simlox.exe"),
    }
    assert set(source) == set(expected)
    assert all(source[key] == sha(path) for key, path in expected.items())
    assert [s["name"] for s in steps] == (["import", "export", "calc", "jsonreport", "check_import_export"]
                                         if variant == "valid-control" else
                                         ["import", "export", "calc", "check_import_export"])
    assert all(s["exit_code"] == 0 and s["gui_preserved"] for s in steps)
    assert load(run / "roundtrip-validation.json")["passed"]
    assert len(closure["raw"]) == (12 if variant == "valid-control" else 9)
    for name, seal in closure["raw"].items():
        path = run / name
        assert path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"]
    return {"run_id": run_id, "variant": variant,
            "role": "accepted_positive_control" if variant == "valid-control" else "accepted_native_rejection",
            "local_path": str(run.resolve()),
            "input_sha256": sha(run / "input.json"),
            "invocation_sha256": sha(run / "invocation.json"),
            "closure_sha256": sha(run / "closure.json"),
            "run_log_sha256": sha(run / "run.log"),
            "report_sha256": sha(run / "report-raw.json") if variant == "valid-control" else None,
            "raw": closure["raw"]}


def main() -> None:
    author = load(HERE / "review/author-matrix-validation-2026-10-02.json")
    if author.get("passed") is not True or [r["variant"] for r in author["runs"]] != list(VARIANTS):
        raise ValueError("author matrix acceptance missing")
    reports = sorted((HERE / "review").glob("independent*.json"))
    if len(reports) != 1:
        raise ValueError("one independent report required")
    independent = load(reports[0])
    verdict = independent.get("verdict", independent.get("decision"))
    independent_passed = (independent.get("checks_passed") == independent.get("checks_total")
                          and independent.get("checks_total", 0) > 0
                          and independent.get("failures") == [])
    if not independent_passed or not isinstance(verdict, str) or not verdict.startswith("GO"):
        raise ValueError(f"independent bounded GO missing: {verdict}")
    runs = [record(variant) for variant in VARIANTS]
    source_files = sorted(p for p in HERE.rglob("*") if p.is_file()
                          and "runs" not in p.relative_to(HERE).parts
                          and "__pycache__" not in p.relative_to(HERE).parts
                          and p.name != "evidence-index.json")
    index = {"schema": "simlox-g02-var05-invalid-ref-evidence-index/v1", "case_id": "G02",
             "variant_id": "G02.var05", "version": "1.0.0",
             "scope": "one fixed-seed native positive control and two localized dangling-reference rejections",
             "source_files_sha256": {p.relative_to(HERE).as_posix(): sha(p) for p in source_files},
             "accepted_runs": runs,
             "parent_input_sha256": sha(PARENT / "native-input.json"),
             "parent_evidence_index_sha256": sha(PARENT / "evidence-index.json"),
             "author_validation_sha256": sha(HERE / "review/author-matrix-validation-2026-10-02.json"),
             "independent_review_sha256": sha(reports[0])}
    raw = (json.dumps(index, indent=2) + "\n").encode("utf-8")
    output = HERE / "evidence-index.json"
    if output.exists() and output.read_bytes() != raw:
        raise ValueError("frozen evidence index differs")
    if not output.exists():
        output.write_bytes(raw)
    print(json.dumps({"index_sha256": sha(output), "accepted_runs": len(runs),
                      "raw_seals": sum(len(r["raw"]) for r in runs)}))


if __name__ == "__main__":
    main()
