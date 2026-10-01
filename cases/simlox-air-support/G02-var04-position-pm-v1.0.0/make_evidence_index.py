"""Freeze G02.var04 accepted and excluded native raw seals after independent review."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ACCEPTED = {
    "no-pm": "g02-var04-no-pm-20261002-02",
    "pos-a-only": "g02-var04-pos-a-only-20261002-02",
    "pos-b-only": "g02-var04-pos-b-only-20261002-01",
    "both": "g02-var04-both-20261002-01",
}
EXCLUDED = {
    "g02-var04-no-pm-20261002-01": "earlier source-bound control before PM task-schema correction",
    "g02-var04-pos-a-only-20261002-01": "incomplete PM task schema; native TaskBreakDown and PMLocation #2010",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def run_record(run_id: str, accepted: bool, variant: str | None = None) -> dict:
    run = HERE / "runs" / run_id
    invocation, closure, steps = (load(run / x) for x in ("invocation.json", "closure.json", "steps.json"))
    assert invocation["run_id"] == closure["run_id"] == run_id
    assert sha(run / "invocation.json") == closure["invocation_sha256"]
    assert closure["source_hashes_before"] == closure["source_hashes_after"]
    assert sha(run / "input.json") == closure["source_hashes_before"]["input"]
    assert all((run / name).stat().st_size == seal["bytes"] and sha(run / name) == seal["sha256"]
               for name, seal in closure["raw"].items())
    if accepted:
        assert invocation["variant"] == variant and closure["error"] is None
        assert sha(HERE / f"{variant}-input.json") == closure["source_hashes_before"]["input"]
        expected = {
            "input": HERE / f"{variant}-input.json",
            "parent": ROOT / "G02-var01-position-modes-v1.0.0/native-input.json",
            "pm_template": ROOT / "D03-calendar-pm-v1.0.0/native-input.json",
            "manual": Path("C:/Program Files/Systecon/SIMLOX/UserDoc/SIMLOX.pdf"),
            "dictionary": Path("C:/Program Files/Systecon/SIMLOX/UserDoc/Table relations/DatabaseDictionary_SIMLOX.txt"),
            "contract": HERE / "contract.json", "builder": HERE / "build.py",
            "checker": HERE / "check_roundtrip.py", "runner_script": HERE / "run_native_ssh.ps1",
            "python": Path("C:/Users/user/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe"),
            "simlox_exe": Path("C:/Program Files/Systecon/SIMLOX/Simlox.exe"),
        }
        assert set(closure["source_hashes_before"]) == set(expected)
        assert all(closure["source_hashes_before"][key] == sha(path) for key, path in expected.items())
        assert [s["name"] for s in steps] == ["import", "export", "calc", "jsonreport", "check_import_export"]
        assert all(s["status"] == "completed" and s["exit_code"] == 0 and s["gui_preserved"] for s in steps)
        assert load(run / "roundtrip-validation.json")["passed"]
        assert len(closure["raw"]) == 12
    return {"run_id": run_id, "variant": invocation["variant"],
            "role": "accepted_fixed_seed_arm" if accepted else "excluded_diagnostic",
            "reason": None if accepted else EXCLUDED[run_id],
            "local_path": str(run.resolve()), "input_sha256": sha(run / "input.json"),
            "invocation_sha256": sha(run / "invocation.json"), "closure_sha256": sha(run / "closure.json"),
            "run_log_sha256": sha(run / "run.log"),
            "report_sha256": sha(run / "report-raw.json") if (run / "report-raw.json").exists() else None,
            "raw": closure["raw"]}


def main() -> None:
    author = load(HERE / "review/author-matrix-validation-2026-10-02.json")
    if author.get("passed") is not True or [r["variant"] for r in author["runs"]] != list(ACCEPTED):
        raise ValueError("author matrix acceptance missing")
    reports = sorted((HERE / "review").glob("independent*.json"))
    if len(reports) != 1:
        raise ValueError("one independent report required")
    independent = load(reports[0])
    verdict = independent.get("verdict", independent.get("decision"))
    independent_passed = (independent.get("passed") is True or
                          (independent.get("checks_passed") == independent.get("checks_total")
                           and independent.get("checks_total", 0) > 0
                           and independent.get("failures") == []))
    if not independent_passed or not isinstance(verdict, str) or not verdict.startswith("GO"):
        raise ValueError(f"independent bounded GO missing: {verdict}")
    accepted = [run_record(run_id, True, variant) for variant, run_id in ACCEPTED.items()]
    excluded = [run_record(run_id, False) for run_id in EXCLUDED]
    source_files = sorted(p for p in HERE.rglob("*") if p.is_file()
                          and "runs" not in p.relative_to(HERE).parts
                          and "__pycache__" not in p.relative_to(HERE).parts
                          and p.name != "evidence-index.json")
    index = {"schema": "simlox-g02-var04-position-pm-evidence-index/v1", "case_id": "G02",
             "variant_id": "G02.var04", "version": "1.0.0",
             "scope": "four fixed-seed position-specific PM arms; two initial diagnostics excluded",
             "source_files_sha256": {p.relative_to(HERE).as_posix(): sha(p) for p in source_files},
             "accepted_runs": accepted, "excluded_diagnostics": excluded,
             "parent_input_sha256": sha(ROOT / "G02-var01-position-modes-v1.0.0/native-input.json"),
             "pm_template_input_sha256": sha(ROOT / "D03-calendar-pm-v1.0.0/native-input.json"),
             "author_validation_sha256": sha(HERE / "review/author-matrix-validation-2026-10-02.json"),
             "independent_review_sha256": sha(reports[0])}
    raw = (json.dumps(index, indent=2) + "\n").encode("utf-8")
    output = HERE / "evidence-index.json"
    if output.exists() and output.read_bytes() != raw:
        raise ValueError("frozen evidence index differs")
    if not output.exists():
        output.write_bytes(raw)
    print(json.dumps({"index_sha256": sha(output), "accepted_runs": len(accepted),
                      "accepted_raw_seals": sum(len(r["raw"]) for r in accepted),
                      "excluded_raw_seals": sum(len(r["raw"]) for r in excluded)}))


if __name__ == "__main__":
    main()
