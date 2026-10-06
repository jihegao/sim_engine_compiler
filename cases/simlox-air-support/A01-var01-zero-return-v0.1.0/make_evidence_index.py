"""Seal zero-return source and accepted parent, both siblings and child."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PARENT = ROOT / "A01-single-aircraft-single-mission"
SIBLING = ROOT / "A01-var01-zero-outbound-v0.1.0"
SIBLING2 = ROOT / "A01-var01-sum-one-v0.1.0"
PARENT_RUN = Path("C:/Users/user/Documents/Codex/2026-09-27/simlox-case-library-a01-a02-v1/repo/data/local/simlox-case-library/v1/A01/a01-bound-final-20260927-03")
SIBLING_RUN = SIBLING / "runs" / "a01-var01-tfout0-v010-ssh-20261006-01"
SIBLING2_RUN = SIBLING2 / "runs" / "a01-var01-sum1-v010-ssh-20261006-01"
CHILD_RUN = HERE / "runs" / "a01-var01-tfret0-v010-ssh-20261006-01"
EXCLUDE = {"evidence-index.json", "cli-scope-signoff-2026-10-06.md", "independent-publication-review-2026-10-06.md"}

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def check(path, expected):
    assert sha(path) == expected, (path, sha(path), expected)

def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))

def seal_parent(contract):
    check(PARENT / "evidence-index.json", contract["accepted_parent"]["evidence_index_sha256"])
    index = load(PARENT / "evidence-index.json")
    assert len(index["runs"]) == 2
    expected = {contract["accepted_parent"]["final_run_id"]: contract["accepted_parent"]["final_closure_sha256"],
                contract["accepted_parent"]["replay_run_id"]: contract["accepted_parent"]["replay_closure_sha256"]}
    result = []
    for entry in index["runs"]:
        assert entry["run_id"] in expected and len(entry["artifacts"]) == 17
        for name, pin in entry["artifacts"].items():
            path = Path(pin["path"])
            assert path.is_file() and path.stat().st_size == pin["bytes"] and sha(path) == pin["sha256"], path
        assert entry["artifacts"]["closure.json"]["sha256"] == expected[entry["run_id"]]
        result.append({"role": "accepted_parent", "run_id": entry["run_id"],
                       "local_run_dir": entry["directory"], "artifacts": entry["artifacts"]})
    assert {r["run_id"] for r in result} == set(expected)
    return result

def seal_closure(role, folder, expected):
    closure_path, invocation_path = folder / "closure.json", folder / "invocation.json"
    check(closure_path, expected)
    closure = load(closure_path)
    assert closure["run_id"] == folder.name and closure["error"] is None
    assert closure["invocation_sha256"] == sha(invocation_path)
    assert closure["source_hashes_before"] == closure["source_hashes_after"]
    assert len(closure["raw"]) == 12
    for name, pin in closure["raw"].items():
        path = folder / name
        assert path.is_file() and path.stat().st_size == pin["bytes"] and sha(path) == pin["sha256"], path
    return {"role": role, "run_id": folder.name, "local_run_dir": str(folder.resolve()),
            "closure": {"bytes": closure_path.stat().st_size, "sha256": expected},
            "invocation": {"bytes": invocation_path.stat().st_size, "sha256": sha(invocation_path)},
            "raw": closure["raw"]}

def main():
    contract = load(HERE / "contract.json")
    assert contract["version"] == "0.1.0-contract-candidate"
    for path, expected in [
        (PARENT / "native-input.json", contract["accepted_parent"]["input_sha256"]),
        (PARENT / "contract.json", contract["accepted_parent"]["contract_sha256"]),
        (PARENT / "cli-scope-signoff-2026-09-29.md", contract["accepted_parent"]["signoff_sha256"]),
        (SIBLING / "native-input.json", contract["published_siblings"][0]["input_sha256"]),
        (SIBLING / "cli-scope-signoff-2026-10-06.md", contract["published_siblings"][0]["signoff_sha256"]),
        (SIBLING / "evidence-index.json", contract["published_siblings"][0]["evidence_index_sha256"]),
        (SIBLING2 / "native-input.json", contract["published_siblings"][1]["input_sha256"]),
        (SIBLING2 / "cli-scope-signoff-2026-10-06.md", contract["published_siblings"][1]["signoff_sha256"]),
        (SIBLING2 / "evidence-index.json", contract["published_siblings"][1]["evidence_index_sha256"]),
        (HERE / "native-input.json", "66f2c6fc9d7e4438514f4965c968e0bc3d11db824fd5682f06d1e7362a1346ef"),
    ]:
        check(path, expected)
    author = load(HERE / "review" / "author-native-validation-2026-10-06.json")
    independent = load(HERE / "review" / "independent-verdict.json")
    assert author["passed"] is True and author["checks_count"] == 4172 and not author["failed"]
    assert independent.get("decision", independent.get("verdict")) == "GO_BOUNDED" and not independent["failures"]
    assert independent["checks"] == 4526 and independent["parent_raw_seals"] == 34 and independent["sibling_raw_seals"] == 12 and independent["second_sibling_raw_seals"] == 12 and independent["child_raw_seals"] == 12
    sources = []
    for path in sorted(HERE.rglob("*")):
        if not path.is_file() or path.name in EXCLUDE or path.suffix == ".pyc":
            continue
        if "runs" in path.relative_to(HERE).parts or "__pycache__" in path.parts:
            continue
        sources.append({"path": path.relative_to(HERE).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)})
    assert len(sources) == len({x["path"] for x in sources})
    runs = seal_parent(contract) + [
        seal_closure("published_zero_outbound_sibling", SIBLING_RUN, contract["published_siblings"][0]["closure_sha256"]),
        seal_closure("published_sum_one_sibling", SIBLING2_RUN, contract["published_siblings"][1]["closure_sha256"]),
        seal_closure("bounded_zero_return_child", CHILD_RUN, "4700b79d6209fc6213810cfa11760687e0fa3e294e2dc4f31532ca1f2fdc8517"),
    ]
    index = {"schema": "simlox-a01-var01-zero-return-v010-evidence-index/v1", "case_id": "A01", "variant_id": "A01.var01",
             "version": "0.1.0", "status": "bounded_zero_return_arm_ready_for_publication",
             "publication_state": "not_published", "source": sources,
             "accepted_parent": contract["accepted_parent"], "published_siblings": contract["published_siblings"],
             "runs": runs, "local_raw_count": 70, "author_checks": 4172,
             "independent_checks": independent["checks"],
             "independent_verdict": {"decision": independent.get("decision", independent.get("verdict")),
                                     "sha256": sha(HERE / "review" / "independent-verdict.json")},
             "scope": "One fixed h8-10 A01 mission, physical aircraft ID0, TFRET 0.25-to0 plus retained TFOUT0.25, task h8.5-10 and h10 mission success, full report parity.",
             "limits": "No travel-geography/general mission/GUI visual/cross-engine/full A01.var01 or Issue18 claim.",
             "raw_location_policy": "local_only_ignored_runs_not_committed"}
    data = (json.dumps(index, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    (HERE / "evidence-index.json").write_bytes(data)
    print(json.dumps({"source_files": len(sources), "local_raw_count": 70,
                      "evidence_index_sha256": hashlib.sha256(data).hexdigest()}))

if __name__ == "__main__":
    main()
