"""Seal the B01 zero-preparation child and accepted B01/A01 local controls."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUN_ID = "b01-var01-zero-prep-v010-ssh-20261006-01"
B01_RUN = Path(
    "C:/Users/user/dev/sim_engine_compiler-b01-v101/cases/simlox-air-support/"
    "B01-fixed-preparation-v1.0.1/runs/b01-v101-ssh-20260929-06"
)
A01_RAW = Path(
    "C:/Users/user/Documents/Codex/2026-09-27/simlox-case-library-a01-a02-v1/"
    "repo/data/local/simlox-case-library/v1/A01"
)
EXCLUDE = {"evidence-index.json", "cli-scope-signoff-2026-10-06.md",
           "independent-staged-go-2026-10-06.md", "independent-remote-pr489-2026-10-06.md"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def pin(path):
    return {"bytes": path.stat().st_size, "sha256": sha(path)}


def source_files():
    result = []
    for path in sorted(HERE.rglob("*")):
        if not path.is_file() or path.name in EXCLUDE or path.suffix == ".pyc":
            continue
        if "runs" in path.relative_to(HERE).parts or "__pycache__" in path.parts:
            continue
        result.append({"path": path.relative_to(HERE).as_posix(), **pin(path)})
    return result


def accepted_b01(entry):
    folder = ROOT / entry["package"]
    for key, name in (("input_sha256", "native-input.json"),
                      ("contract_sha256", "contract.json"),
                      ("publication_sha256", "evidence-2026-09-29.md"),
                      ("independent_review_sha256", "review/independent-readonly-rerun-2026-09-29.json")):
        assert sha(folder / name) == entry[key], name
    assert sha(folder / "parent-diff.json") == "79c801e621e6872b823e9558d3b9bdb2fe0555acdce34bb33147698695c9bb92"
    closure_path = B01_RUN / "closure.json"
    assert sha(closure_path) == entry["closure_sha256"]
    closure = load(closure_path)
    assert closure["run_id"] == entry["run_id"] and not closure.get("error")
    assert len(closure["raw"]) == 11
    for name, artifact in closure["raw"].items():
        assert pin(B01_RUN / name) == artifact, name
    return {"role": "accepted_b01", "run_id": entry["run_id"],
            "local_run_dir": str(B01_RUN), "closure": pin(closure_path),
            "raw": closure["raw"]}


def accepted_a01(entry):
    folder = ROOT / "A01-single-aircraft-single-mission"
    assert sha(folder / "native-input.json") == entry["input_sha256"]
    assert sha(folder / "cli-scope-signoff-2026-09-29.md") == entry["signoff_sha256"]
    index_path = folder / "evidence-index.json"
    assert sha(index_path) == "2fe2383e513b0e59c581d5e7b48ec8da000a674a9f41e257b0e4f91836deb880"
    index = load(index_path)
    expected = {
        "a01-bound-final-20260927-03": "7e253f9acdeed55197e191530f7e9ad8d88abe387326fd7b4c5152da3529288e",
        "a01-bound-replay-20260927-04": "3781103d253f08c6d3f8f84572877f6b65319a18c10a9e40736e608f829811ee",
    }
    assert len(index["runs"]) == 2
    result = []
    for run in index["runs"]:
        assert run["run_id"] in expected and len(run["artifacts"]) == 17
        for name, artifact in run["artifacts"].items():
            path = Path(artifact["path"])
            assert pin(path) == {"bytes": artifact["bytes"], "sha256": artifact["sha256"]}, name
        closure_path = A01_RAW / run["run_id"] / "closure.json"
        assert sha(closure_path) == expected[run["run_id"]]
        result.append({"role": "accepted_a01", "run_id": run["run_id"],
                       "local_run_dir": run["directory"], "artifacts": run["artifacts"]})
    assert {x["run_id"] for x in result} == set(expected)
    return result


def child():
    run = HERE / "runs" / RUN_ID
    closure_path = run / "closure.json"
    closure = load(closure_path)
    assert closure["run_id"] == RUN_ID and closure["error"] is None
    assert closure["source_hashes_before"] == closure["source_hashes_after"]
    assert closure["invocation_sha256"] == sha(run / "invocation.json")
    assert len(closure["raw"]) == 12
    for name, artifact in closure["raw"].items():
        assert pin(run / name) == artifact, name
    return {"role": "bounded_b01_zero_preparation_child", "run_id": RUN_ID,
            "local_run_dir": str(run.resolve()), "closure": pin(closure_path),
            "invocation": pin(run / "invocation.json"), "raw": closure["raw"]}


def main():
    contract = load(HERE / "contract.json")
    assert contract["version"] == "0.1.0-contract-candidate"
    author = load(HERE / "review/author-validation.json")
    independent = load(HERE / "review/independent-verdict.json")
    assert author["decision"] == "GO_BOUNDED" and author["checks"] == 4600 and not author["failures"]
    assert independent["decision"] == "GO_BOUNDED" and not independent["failures"]
    assert isinstance(independent["checks"], int) and independent["checks"] > 4000
    runs = accepted_a01(contract["instructional_prerequisite"])
    runs.append(accepted_b01(contract["accepted_parent"]))
    runs.append(child())
    result = {
        "schema": "simlox-b01-var01-zero-preparation-evidence-index/v1",
        "case_id": "B01", "variant_id": "B01.var01", "version": "0.1.0",
        "status": "bounded_zero_preparation_ready_for_publication",
        "publication_state": "not_published", "source": source_files(),
        "accepted_parent": contract["accepted_parent"],
        "instructional_prerequisite": contract["instructional_prerequisite"],
        "runs": runs, "accepted_a01_raw_count": 34, "accepted_b01_raw_count": 11,
        "child_raw_count": 12, "author_checks": author["checks"],
        "independent_checks": independent["checks"],
        "independent_verdict": {"decision": independent["decision"],
                                "sha256": sha(HERE / "review/independent-verdict.json")},
        "scope": "One fixed-seed B01 PREP-FIXED row with DURN zero and complete report reconciliation.",
        "limits": "One seed/aircraft/mission/task; stale Tasks.DESCR, no general zero-duration, resources, GUI visual, cross-engine, full B01.var01 or Issue18 claim.",
        "raw_location_policy": "local_only_ignored_runs_not_committed",
    }
    data = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    (HERE / "evidence-index.json").write_bytes(data)
    print(json.dumps({"index_sha256": hashlib.sha256(data).hexdigest(),
                      "source_files": len(result["source"]), "local_raw_count": 57}))


if __name__ == "__main__":
    main()
