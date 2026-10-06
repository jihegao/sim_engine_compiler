"""Seal three versioned analyses and three existing local native runs."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
V020 = ROOT / "D04-var01-over-threshold-v0.2.0"
V021 = ROOT / "D04-var01-over-threshold-reanalysis-v0.2.1"
PARENT = ROOT / "D04-flight-hour-pm-v1.0.0" / "runs" / "d04-flight-v100-ssh-20260930-01"
SIBLING = ROOT / "D04-var01-threshold-not-reached-v0.1.1" / "runs" / "d04-var01-op4-v011-ssh-20261006-01"
CHILD = V020 / "runs" / "d04-var01-op2-v020-ssh-20261006-01"
EXCLUDE = {"evidence-index.json", "cli-scope-signoff-2026-10-06.md", "independent-publication-review-2026-10-06.md"}

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def check(path, expected):
    assert sha(path) == expected, (path, expected, sha(path))

def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))

def seal(role, folder, expected):
    closure_path = folder / "closure.json"
    invocation_path = folder / "invocation.json"
    check(closure_path, expected)
    closure = load(closure_path)
    assert closure["error"] is None and closure["run_id"] == folder.name
    check(invocation_path, closure["invocation_sha256"])
    assert closure["source_hashes_before"] == closure["source_hashes_after"]
    assert len(closure["raw"]) == 12
    for name, pin in closure["raw"].items():
        path = folder / name
        assert path.stat().st_size == pin["bytes"] and sha(path) == pin["sha256"], path
    return {"role": role, "run_id": folder.name, "local_run_dir": str(folder.resolve()),
            "closure": {"bytes": closure_path.stat().st_size, "sha256": expected},
            "invocation": {"bytes": invocation_path.stat().st_size, "sha256": sha(invocation_path)},
            "raw": closure["raw"]}

def main():
    contract = load(HERE / "contract.json")
    assert contract["version"] == "0.2.2-readonly-candidate"
    v020 = contract["sealed_run"]
    check(V020 / "contract.json", v020["contract_sha256"])
    check(V020 / "native-input.json", v020["input_sha256"])
    failed020 = contract["preserved_failed_v020"]
    check(V020 / "validate_native_cli.py", failed020["validator_sha256"])
    check(V020 / "review" / "failed-author-serialization-2026-10-06.txt", failed020["failure_log_sha256"])
    failed021 = contract["preserved_failed_v021"]
    check(V021 / "contract.json", failed021["contract_sha256"])
    check(V021 / "validate_readonly.py", failed021["checker_sha256"])
    check(V021 / "review" / "author-readonly-validation-2026-10-06.json", failed021["author_verdict_sha256"])
    author = load(HERE / "review" / "author-readonly-validation-2026-10-06.json")
    independent = load(HERE / "review" / "independent-verdict.json")
    assert author["passed"] is True and author["checks_count"] == 7068
    assert independent["verdict"] == "GO_BOUNDED" and independent["checks_count"] == 7376
    assert independent["checks_passed"] == 7376 and not independent["failures"]
    sources = []
    for version in (V020, V021, HERE):
        for path in sorted(version.rglob("*")):
            if not path.is_file() or path.name in EXCLUDE or path.suffix == ".pyc":
                continue
            if "runs" in path.relative_to(version).parts or "__pycache__" in path.parts:
                continue
            sources.append({"path": path.relative_to(ROOT).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)})
    assert len(sources) == len({x["path"] for x in sources})
    runs = [
        seal("accepted_parent_op_hours_three", PARENT, "3cae72c375ef7a7c8dc63d785a33e97e9bd6103655fc28971abf5a0ccb24df45"),
        seal("published_sibling_op_hours_four", SIBLING, contract["accepted_sibling_closure_sha256"]),
        seal("bounded_child_op_hours_two", CHILD, v020["closure_sha256"]),
    ]
    index = {"schema": "simlox-d04-var01-v022-evidence-index/v1", "case_id": "D04", "variant_id": "D04.var01",
             "version": "0.2.2", "status": "bounded_fixed_three_threshold_panel_ready_for_publication",
             "publication_state": "not_published", "source": sources,
             "sealed_run": v020, "preserved_failed_v020": failed020, "preserved_failed_v021": failed021,
             "runs": runs, "local_raw_count": 36, "author_checks": 7068,
             "independent_verdict": independent,
             "scope": "One seed, aircraft and two-mission schedule; OPHOURS2 child h10-11 sole PM, accepted OPHOURS3 parent h41-42 PM and published OPHOURS4 sibling no PM through h60.",
             "limits": "v0.2.0/v0.2.1 failed verdicts excluded; no direct PM counter, second full post-repair PM cycle, general threshold, GUI visual, cross-engine or overall Issue18 claim.",
             "raw_location_policy": "local_only_ignored_runs_not_committed"}
    data = (json.dumps(index, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    (HERE / "evidence-index.json").write_bytes(data)
    print(json.dumps({"source_files": len(sources), "local_raw_count": 36,
                      "evidence_index_sha256": hashlib.sha256(data).hexdigest()}))

if __name__ == "__main__":
    main()
