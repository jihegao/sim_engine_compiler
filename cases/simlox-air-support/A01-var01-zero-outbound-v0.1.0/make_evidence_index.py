"""Seal the bounded A01 child, frozen source and both accepted parent runs."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PARENT = ROOT / "A01-single-aircraft-single-mission"
CHILD_RUN = HERE / "runs" / "a01-var01-tfout0-v010-ssh-20261006-01"
EXCLUDE = {"evidence-index.json", "cli-scope-signoff-2026-10-06.md", "independent-publication-review-2026-10-06.md"}

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def check(path, expected):
    assert sha(path) == expected, (path, sha(path), expected)

def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))

def seal_parent():
    index_path = PARENT / "evidence-index.json"
    check(index_path, "2fe2383e513b0e59c581d5e7b48ec8da000a674a9f41e257b0e4f91836deb880")
    index = load(index_path)
    assert len(index["runs"]) == 2
    expected = {
        "a01-bound-final-20260927-03": "7e253f9acdeed55197e191530f7e9ad8d88abe387326fd7b4c5152da3529288e",
        "a01-bound-replay-20260927-04": "3781103d253f08c6d3f8f84572877f6b65319a18c10a9e40736e608f829811ee",
    }
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

def seal_child():
    closure_path = CHILD_RUN / "closure.json"
    invocation_path = CHILD_RUN / "invocation.json"
    expected = "ea378b70e1e5af5f37b47dc2dd20a4318943fdb24a1608745eccf549eda809af"
    check(closure_path, expected)
    closure = load(closure_path)
    assert closure["run_id"] == CHILD_RUN.name and closure["error"] is None
    assert closure["invocation_sha256"] == sha(invocation_path)
    assert closure["source_hashes_before"] == closure["source_hashes_after"]
    assert len(closure["raw"]) == 12
    for name, pin in closure["raw"].items():
        path = CHILD_RUN / name
        assert path.is_file() and path.stat().st_size == pin["bytes"] and sha(path) == pin["sha256"], path
    return {"role": "bounded_child", "run_id": CHILD_RUN.name,
            "local_run_dir": str(CHILD_RUN.resolve()),
            "closure": {"bytes": closure_path.stat().st_size, "sha256": expected},
            "invocation": {"bytes": invocation_path.stat().st_size, "sha256": sha(invocation_path)},
            "raw": closure["raw"]}

def main():
    contract = load(HERE / "contract.json")
    assert contract["version"] == "0.1.0-contract-candidate"
    check(PARENT / "native-input.json", contract["accepted_parent"]["input_sha256"])
    check(PARENT / "contract.json", contract["accepted_parent"]["contract_sha256"])
    check(PARENT / "cli-scope-signoff-2026-09-29.md", contract["accepted_parent"]["signoff_sha256"])
    check(HERE / "native-input.json", "ac0c134a34362c2cec6ec6c51a90b0f81a7d21b229e8ec76a2595a818d14e3ea")
    author = load(HERE / "review" / "author-native-validation-2026-10-06.json")
    independent = load(HERE / "review" / "independent-verdict.json")
    assert author["passed"] is True and author["checks_count"] == 4113 and not author["failed"]
    assert independent["decision"] == "GO_BOUNDED" and not independent["failures"]
    assert independent["checks"] == 4480 and independent["child_raw_seals"] == 12 and independent["parent_raw_seals"] == 34
    sources = []
    for path in sorted(HERE.rglob("*")):
        if not path.is_file() or path.name in EXCLUDE or path.suffix == ".pyc":
            continue
        if "runs" in path.relative_to(HERE).parts or "__pycache__" in path.parts:
            continue
        sources.append({"path": path.relative_to(HERE).as_posix(), "bytes": path.stat().st_size, "sha256": sha(path)})
    assert len(sources) == len({x["path"] for x in sources})
    runs = seal_parent() + [seal_child()]
    index = {"schema": "simlox-a01-var01-v010-evidence-index/v1", "case_id": "A01", "variant_id": "A01.var01",
             "version": "0.1.0", "status": "bounded_zero_outbound_arm_ready_for_publication",
             "publication_state": "not_published", "source": sources,
             "accepted_parent": contract["accepted_parent"], "runs": runs, "local_raw_count": 46,
             "author_checks": 4113, "independent_checks": 4480,
             "independent_verdict": {"decision": independent["decision"], "sha256": sha(HERE / "review" / "independent-verdict.json")},
             "scope": "One fixed h8-10 A01 mission, physical aircraft ID0, TFOUT 0.25-to0 with TFRET 0.25 retained; task start h8 and completion h9.5; all native report rows match accepted parent.",
             "limits": "No sum-to-one or TFRET-zero boundary, travel-geography/general mission/GUI visual/cross-engine/full A01.var01 or Issue18 claim.",
             "raw_location_policy": "local_only_ignored_runs_not_committed"}
    data = (json.dumps(index, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    (HERE / "evidence-index.json").write_bytes(data)
    print(json.dumps({"source_files": len(sources), "local_raw_count": 46,
                      "evidence_index_sha256": hashlib.sha256(data).hexdigest()}))

if __name__ == "__main__":
    main()
