"""Seal reviewed D01.var03 sources, accepted raw runs and excluded precursor."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OLD = ROOT / "D01-var03-terminal-repair-v0.1.0"
OUTPUT = HERE / "evidence-index.json"
PARENT = ROOT / "D01-system-direct-repair-v1.0.0" / "runs" / "d01-v100-ssh-20260929-01"
CHILD = HERE / "runs" / "d01-var03-terminal-v011-ssh-20261006-01"
FAILED = OLD / "runs" / "d01-var03-terminal-v010-ssh-20261006-01"
RUNS = (("parent", PARENT, "c3769da04ae3e8e754ff172cb0bed9317a0ec7ec5352913086341cc0ad489c05"),
        ("child", CHILD, "d17ef79e8d832a5c89197ce35d97e8a0245f2ce8194e61b7d4ddabc45b8d7195"))
LINEAGE = (
    ("accepted_parent", "D01", ROOT / "D01-system-direct-repair-v1.0.0" / "cli-scope-signoff-2026-09-29.md", "428224849277100ebd7b97f068308e43617884759cb3a82e1792ddebeae772b3"),
    ("instructional_prerequisite", "A02", ROOT / "A02-single-aircraft-repeated-missions" / "cli-scope-signoff-2026-09-29.md", "608eef828a65ef7a8c738a3ec227b890421c29248ee8addd9e992a4c7e7e919e"),
    ("collection_precedent", "J05.var01", ROOT / "J05-collection-window-v1.0.1" / "cli-scope-signoff-2026-10-01.md", "8c30b1b1a563c2350431fe7978eea12ae8c33bd112584dc3b53006d509ba9e95"),
    ("terminal_repair_precedent", "D05.var04", ROOT / "D05-var04-horizon-in-repair-v1.0.0" / "cli-scope-signoff-2026-09-30.md", "6a6f2c82c027e84fee22b8895f2bb53d4af2d65749846a76a074a0abab2ae22f"),
)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def source_files(package: Path) -> list[dict]:
    result = []
    for path in sorted(package.rglob("*")):
        if (not path.is_file() or path == OUTPUT or
                path.name in ("cli-scope-signoff-2026-10-06.md",
                              "independent-publication-review-2026-10-06.md") or
                "runs" in path.parts or "__pycache__" in path.parts or path.suffix == ".pyc"):
            continue
        result.append({"path": path.relative_to(package).as_posix(),
                       "bytes": path.stat().st_size, "sha256": sha(path)})
    return result


def sealed_run(role: str, run: Path, expected_closure: str) -> dict:
    closure_path, invocation_path = run / "closure.json", run / "invocation.json"
    assert sha(closure_path) == expected_closure, closure_path
    closure = load(closure_path)
    assert closure["run_id"] == run.name and closure["invocation_sha256"] == sha(invocation_path)
    assert closure["error"] is None and closure["source_hashes_before"] == closure["source_hashes_after"]
    assert len(closure["raw"]) == 12
    for name, seal in closure["raw"].items():
        path = run / name
        assert path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"], path
    return {"role": role, "run_id": run.name, "local_run_dir": str(run.resolve()),
            "invocation": {"bytes": invocation_path.stat().st_size, "sha256": sha(invocation_path)},
            "closure": {"bytes": closure_path.stat().st_size, "sha256": expected_closure},
            "raw": closure["raw"]}


def excluded_run() -> dict:
    closure_path, failure_path, invocation_path = (FAILED / name for name in
                                                  ("closure.json", "failure-seal.json", "invocation.json"))
    assert sha(closure_path) == "dadd724454ec461a83e75946b54cb4a50e7cee57b777ad00cf842949a4dce5f2"
    assert sha(failure_path) == "40fde15b06ae281cd0c6042ee02ad1ae510e0e6554aea156aac9ffcbba9e51a1"
    closure, failure = load(closure_path), load(failure_path)
    assert closure["run_id"] == FAILED.name and closure["invocation_sha256"] == sha(invocation_path)
    assert closure["source_hashes_before"] == closure["source_hashes_after"]
    assert closure["error"] == "calc output model.sxo absent/empty" and len(closure["raw"]) == 9
    assert len(failure["files"]) == 11 and failure["error"] == closure["error"]
    for record in (closure["raw"], failure["files"]):
        for name, seal in record.items():
            path = FAILED / name
            assert path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"], path
    assert "(error #204) Some missions may not return before simulation period ends" in (FAILED / "run.log").read_text(encoding="utf-8-sig")
    return {"status": "excluded_converter_error_204", "run_id": FAILED.name,
            "local_run_dir": str(FAILED.resolve()),
            "invocation": {"bytes": invocation_path.stat().st_size, "sha256": sha(invocation_path)},
            "closure": {"bytes": closure_path.stat().st_size, "sha256": sha(closure_path)},
            "failure_seal": {"bytes": failure_path.stat().st_size, "sha256": sha(failure_path)},
            "raw": closure["raw"], "all_failed_files": failure["files"]}


def main() -> None:
    source = source_files(HERE)
    old_source = source_files(OLD)
    lineage = []
    for role, case_id, path, expected in LINEAGE:
        assert sha(path) == expected, path
        lineage.append({"role": role, "case_id": case_id, "signoff_path": str(path.resolve()),
                        "signoff_bytes": path.stat().st_size, "signoff_sha256": expected})
    runs = [sealed_run(*entry) for entry in RUNS]
    failed = excluded_run()
    original = load(HERE / "review" / "author-native-validation-2026-10-06.json")
    corrected = load(HERE / "review" / "author-readonly-replay-v012-2026-10-06.json")
    independent = load(HERE / "review" / "independent-verdict.json")
    assert original["passed"] is False and original["checks"] == 604 and original["differences"] == [
        "system bin 80 full ledger", "system bin 83 full ledger"]
    assert corrected["passed"] is True and corrected["checks"] == 605 and corrected["differences"] == []
    assert independent["verdict"] == "GO_BOUNDED" and independent["checks"] == 721 and independent["failed"] == []
    index = {
        "schema": "simlox-d01-var03-v011-evidence-index/v1", "case_id": "D01", "variant_id": "D01.var03",
        "version": "0.1.1", "status": "native_behavior_accepted_cli_scope_ready_for_publication",
        "publication_state": "not_published", "source": source, "excluded_precursor_source": old_source,
        "lineage": lineage, "accepted_runs": runs, "accepted_raw_count": 24,
        "excluded_precursor_run": failed,
        "author_original_result": "failed_602_of_604_preserved",
        "author_corrected_checks": 605, "independent_checks": 721,
        "scope": "one seeded direct system repair still active at hour 34.375 after three scheduled missions",
        "limits": "One seed, one native executable, one aircraft and a shortened horizon. No post-horizon completion, generic scheduling or same-time priority, GUI visual, cross-engine, stocked-item, or overall D01/Issue18 claim. PNB is aggregate. Excluded v0.1.0 #204 and original strict author-bin prediction remain preserved.",
        "raw_location_policy": "local_only_ignored_runs_not_committed",
    }
    raw = (json.dumps(index, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    OUTPUT.write_bytes(raw)
    print(json.dumps({"source_files": len(source), "excluded_source_files": len(old_source),
                      "accepted_raw": 24, "excluded_raw": 9,
                      "evidence_index_sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
