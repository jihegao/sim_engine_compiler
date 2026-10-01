"""Freeze reviewed E07 item-specific SLOW sources and native raw identities."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUN_ID = "e07-item-slow-v100-ssh-20261002-01"
RUN = HERE / "runs" / RUN_ID
PARENT_RUN = ROOT / "E07-item-specific-transport-v1.0.1/runs/e07-item-route-v101-20261001-01"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main() -> None:
    author = load(HERE / "author-validation.json")
    assert author["passed"] and author["checks"] == 28 and not author["differences"]
    assert author["run_id"] == RUN_ID
    reviews = sorted((HERE / "review").glob("independent*.json"))
    assert len(reviews) == 1, "one separate read-only reviewer verdict required"
    review = load(reviews[0])
    verdict = str(review.get("verdict", review.get("decision", ""))).upper()
    passed = review.get("passed") is True or (
        review.get("checks_passed") == review.get("checks_total")
        and review.get("checks_total", 0) > 0 and not review.get("failures"))
    assert passed and verdict.startswith("GO"), "bounded independent GO required"
    invocation, closure, steps = (load(RUN / name) for name in ("invocation.json", "closure.json", "steps.json"))
    assert invocation["run_id"] == closure["run_id"] == RUN_ID
    assert sha(RUN / "invocation.json") == closure["invocation_sha256"]
    assert closure["error"] is None and closure["source_hashes_before"] == closure["source_hashes_after"]
    expected = {
        "input": HERE / "native-input.json",
        "parent": ROOT / "E07-item-specific-transport-v1.0.1/native-input.json",
        "support": ROOT / "E04-upstream-transport-fast-v1.0.0/native-input.json",
        "table_dictionary": Path("C:/Program Files/Systecon/SIMLOX/UserDoc/Table relations/DatabaseDictionary_SIMLOX.txt"),
        "manual": Path("C:/Program Files/Systecon/SIMLOX/UserDoc/SIMLOX.pdf"),
        "contract": HERE / "contract.json", "builder": HERE / "build.py",
        "exact_diff": HERE / "exact-diff.json", "diff_checker": HERE / "describe_diff.py",
        "checker": HERE / "check_roundtrip.py",
        "python": Path("C:/Users/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe"),
        "runner_script": HERE / "run_native_ssh.ps1",
        "simlox_exe": Path("C:/Program Files/Systecon/SIMLOX/Simlox.exe"),
    }
    assert set(closure["source_hashes_before"]) == set(expected)
    assert all(closure["source_hashes_before"][name] == sha(path) for name, path in expected.items())
    assert [step["name"] for step in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"]
    assert all(step["status"] == "completed" and step["exit_code"] == 0 and step["gui_preserved"] for step in steps)
    assert load(RUN / "roundtrip-validation.json")["passed"]
    assert len(closure["raw"]) == 12
    assert all((RUN / name).stat().st_size == seal["bytes"] and sha(RUN / name) == seal["sha256"]
               for name, seal in closure["raw"].items())
    assert sha(PARENT_RUN / "closure.json") == "c73b4316c0fc44ad31484a7a4eab73d60294d3f054f20d1691cca008d85b64cd"
    files = sorted(path for path in HERE.rglob("*") if path.is_file()
                   and "runs" not in path.relative_to(HERE).parts
                   and "__pycache__" not in path.relative_to(HERE).parts
                   and path.name != "evidence-index.json")
    index = {"schema": "simlox-e07-var01-item-slow-evidence-index/v1",
             "case_id": "E07", "variant_id": "E07.var01", "version": "1.0.0",
             "scope": "one fixed-seed item-specific SLOW support link",
             "source_files_sha256": {path.relative_to(HERE).as_posix(): sha(path) for path in files},
             "accepted_run": {"run_id": RUN_ID, "local_path": str(RUN.resolve()),
                              "input_sha256": sha(RUN / "input.json"),
                              "invocation_sha256": sha(RUN / "invocation.json"),
                              "closure_sha256": sha(RUN / "closure.json"),
                              "model_log_sha256": sha(RUN / "model.log"),
                              "report_sha256": sha(RUN / "report-raw.json"), "raw": closure["raw"]},
             "accepted_fast_parent": {"run_id": PARENT_RUN.name,
                                      "closure_sha256": sha(PARENT_RUN / "closure.json"),
                                      "model_log_sha256": sha(PARENT_RUN / "model.log"),
                                      "report_sha256": sha(PARENT_RUN / "report-raw.json")},
             "author_validation_sha256": sha(HERE / "author-validation.json"),
             "independent_review_sha256": sha(reviews[0])}
    data = (json.dumps(index, indent=2) + "\n").encode("utf-8")
    output = HERE / "evidence-index.json"
    if output.exists() and output.read_bytes() != data:
        raise ValueError("frozen evidence index differs")
    if not output.exists():
        output.write_bytes(data)
    print(json.dumps({"index_sha256": sha(output), "raw_seals": len(closure["raw"]),
                      "independent_review_sha256": sha(reviews[0])}))


if __name__ == "__main__":
    main()
