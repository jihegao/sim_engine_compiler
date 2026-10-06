"""Seal B02.var01 source and its accepted B02/B01 and child local raw evidence."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUN_ID = "b02-var01-zero-step-v010-ssh-20261006-01"
B02_RUN = Path("C:/Users/user/dev/sim_engine_compiler-b02-v102/cases/simlox-air-support/"
               "B02-serial-preparation-v1.0.2/runs/b02-v102-ssh-20260929-01")
B01_RUN = Path("C:/Users/user/dev/sim_engine_compiler-b01-v101/cases/simlox-air-support/"
               "B01-fixed-preparation-v1.0.1/runs/b01-v101-ssh-20260929-06")
EXCLUDE = {"evidence-index.json", "cli-scope-signoff-2026-10-06.md",
           "independent-staged-go-2026-10-06.md", "independent-remote-pr490-2026-10-06.md"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pin(path):
    return {"bytes": path.stat().st_size, "sha256": sha(path)}


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def source_files():
    result = []
    for path in sorted(HERE.rglob("*")):
        if not path.is_file() or path.name in EXCLUDE or path.suffix == ".pyc":
            continue
        if "runs" in path.relative_to(HERE).parts or "__pycache__" in path.parts:
            continue
        result.append({"path": path.relative_to(HERE).as_posix(), **pin(path)})
    return result


def accepted(role, folder, closure_sha, run_id, input_sha):
    closure_path = folder / "closure.json"
    assert sha(closure_path) == closure_sha
    closure = load(closure_path)
    assert closure["run_id"] == run_id and closure["input_sha256"] == input_sha
    assert not closure.get("error") and len(closure["raw"]) == 11
    for name, seal in closure["raw"].items():
        assert pin(folder / name) == seal, (role, name)
    return {"role": role, "run_id": run_id, "local_run_dir": str(folder),
            "closure": pin(closure_path), "raw": closure["raw"]}


def child():
    folder = HERE / "runs" / RUN_ID
    closure_path = folder / "closure.json"
    closure = load(closure_path)
    assert closure["run_id"] == RUN_ID and closure["error"] is None
    assert closure["source_hashes_before"] == closure["source_hashes_after"]
    assert closure["invocation_sha256"] == sha(folder / "invocation.json")
    assert len(closure["raw"]) == 12
    for name, seal in closure["raw"].items():
        assert pin(folder / name) == seal, name
    return {"role": "bounded_b02_zero_first_step_child", "run_id": RUN_ID,
            "local_run_dir": str(folder.resolve()), "closure": pin(closure_path),
            "invocation": pin(folder / "invocation.json"), "raw": closure["raw"]}


def main():
    contract = load(HERE / "contract.json")
    assert contract["version"] == "0.1.0-contract-candidate"
    parent = contract["accepted_parent"]
    for key, name in (("input_sha256", "native-input.json"),
                      ("contract_sha256", "contract.json"),
                      ("publication_sha256", "evidence-2026-09-29.md"),
                      ("independent_review_sha256", "review/independent-readonly-2026-09-29.json")):
        assert sha(ROOT / parent["package"] / name) == parent[key], name
    assert sha(ROOT / "B01-fixed-preparation-v1.0.1/native-input.json") == contract["instructional_prerequisite"]["input_sha256"]
    original = load(HERE / "review/author-validation-v010-no-go.json")
    corrected = load(HERE / "review/author-validation-v011.json")
    independent = load(HERE / "review/independent-verdict.json")
    assert original["decision"] == "NO_GO" and len(original["failures"]) == 2
    assert corrected["decision"] == "GO_BOUNDED" and corrected["checks"] == 4559 and not corrected["failures"]
    assert independent["decision"] == "GO_BOUNDED" and not independent["failures"]
    runs = [accepted("accepted_b01_prerequisite", B01_RUN,
                     contract["instructional_prerequisite"]["closure_sha256"],
                     "b01-v101-ssh-20260929-06",
                     contract["instructional_prerequisite"]["input_sha256"]),
            accepted("accepted_b02_parent", B02_RUN, parent["closure_sha256"],
                     parent["run_id"], parent["input_sha256"]), child()]
    result = {
        "schema": "simlox-b02-var01-zero-step-evidence-index/v1",
        "case_id": "B02", "variant_id": "B02.var01", "version": "0.1.0",
        "publication_state": "not_published", "source": source_files(),
        "accepted_parent": parent, "instructional_prerequisite": contract["instructional_prerequisite"],
        "runs": runs, "accepted_b01_raw_count": 11, "accepted_b02_raw_count": 11,
        "child_raw_count": 12, "original_author_no_go_sha256": sha(HERE / "review/author-validation-v010-no-go.json"),
        "corrected_author_checks": corrected["checks"], "independent_checks": independent["checks"],
        "independent_verdict": {"decision": independent["decision"],
                                "sha256": sha(HERE / "review/independent-verdict.json")},
        "scope": "One fixed-seed B02 ordered preparation with an observable zero-duration first subtask and a positive second subtask.",
        "limits": "One seed/aircraft/mission/two subtasks, stale Tasks.DESCR and overridden main scalar; no general zero-duration, resource wait, GUI visual, cross-engine, full B02.var01 or Issue18 claim.",
        "raw_location_policy": "local_only_ignored_runs_not_committed",
    }
    data = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    (HERE / "evidence-index.json").write_bytes(data)
    print(json.dumps({"index_sha256": hashlib.sha256(data).hexdigest(),
                      "source_files": len(result["source"]), "local_raw_count": 34}))


if __name__ == "__main__":
    main()
