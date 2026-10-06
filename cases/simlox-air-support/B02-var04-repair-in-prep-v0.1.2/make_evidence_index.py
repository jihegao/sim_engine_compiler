"""Seal the B02.var04 source versions and local accepted/negative raw files."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUN_ID = "b02-var04-repair-prep-v012-ssh-20261006-01"
B02_RUN = Path("C:/Users/user/dev/sim_engine_compiler-b02-v102/cases/simlox-air-support/"
               "B02-serial-preparation-v1.0.2/runs/b02-v102-ssh-20260929-01")
B01_RUN = Path("C:/Users/user/dev/sim_engine_compiler-b01-v101/cases/simlox-air-support/"
               "B01-fixed-preparation-v1.0.1/runs/b01-v101-ssh-20260929-06")
OLD = [ROOT / "B02-var04-repair-in-prep-v0.1.0",
       ROOT / "B02-var04-repair-in-prep-v0.1.1"]
EXCLUDE = {"evidence-index.json", "cli-scope-signoff-2026-10-06.md",
           "independent-staged-go-2026-10-06.md", "independent-remote-pr-2026-10-06.md"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pin(path):
    return {"bytes": path.stat().st_size, "sha256": sha(path)}


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def source_files():
    result = []
    for folder in [*OLD, HERE]:
        for path in sorted(folder.rglob("*")):
            if not path.is_file() or path.name in EXCLUDE or path.suffix == ".pyc":
                continue
            if "runs" in path.relative_to(folder).parts or "__pycache__" in path.parts:
                continue
            relative = (path.relative_to(HERE) if folder == HERE else
                        Path("..") / folder.name / path.relative_to(folder))
            result.append({"path": relative.as_posix(), **pin(path)})
    return result


def accepted(role, folder, closure_sha, run_id):
    closure_path = folder / "closure.json"
    assert sha(closure_path) == closure_sha, role
    closure = load(closure_path)
    assert closure["run_id"] == run_id and not closure.get("error")
    assert len(closure["raw"]) == 11
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
    assert len(closure["raw"]) == 10
    for name, seal in closure["raw"].items():
        assert pin(folder / name) == seal, name
    verdict = load(folder / "negative-validation.json")
    assert verdict["decision"] == "GO_BOUNDED" and verdict["passed"]
    assert verdict["diagnostic"]["form"] == "MissionPreparation"
    assert verdict["diagnostic"]["record"] == 1
    assert verdict["diagnostic"]["code"] == 165
    assert not (folder / "model.log").exists() and not (folder / "report-raw.json").exists()
    assert (folder / "model.sxo").stat().st_size == 4
    return {"role": "bounded_b02_var04_converter_negative_child", "run_id": RUN_ID,
            "local_run_dir": str(folder.resolve()), "closure": pin(closure_path),
            "invocation": pin(folder / "invocation.json"), "raw": closure["raw"]}


def main():
    contract = load(HERE / "contract.json")
    assert contract["version"] == "0.1.2-contract-candidate"
    assert sha(HERE / "native-input.json") == contract["source_delta"]["child_input_sha256"]
    assert sha(OLD[0] / "contract.json") == "3b74c74e2214496c43321eb78553ba9060ecdcbe74cef25f16bc6e08cd008e2f"
    assert sha(OLD[1] / "contract.json") == "6e1db85193abcb16e0de66589e74d077076985f5fefb5dd53b0177627b66048e"
    assert sha(OLD[0] / "review/independent-prelaunch-no-go-2026-10-06.md") == "3daecfa33fbd90ef0132093ac83f17f754130dbee9a91637205b6a7171f24b6b"
    assert sha(OLD[1] / "review/independent-prelaunch-no-go-2026-10-06.md") == "bc7c0f4c4dc045b6c5208742b477ff489a9ab38fc92f3eeeb6d935d1ce0b3e9f"
    assert not (OLD[0] / "runs").exists() and not (OLD[1] / "runs").exists()
    independent = load(HERE / "review/independent-verdict.json")
    assert independent["decision"] == "GO_BOUNDED" and not independent.get("problems")
    runs = [accepted("accepted_b01_prerequisite", B01_RUN,
                     contract["instructional_prerequisite"]["closure_sha256"],
                     contract["instructional_prerequisite"]["run_id"]),
            accepted("accepted_b02_parent", B02_RUN,
                     contract["accepted_parent"]["closure_sha256"],
                     contract["accepted_parent"]["run_id"]), child()]
    result = {"schema": "simlox-b02-var04-repair-prep-evidence-index/v1",
              "case_id": "B02", "variant_id": "B02.var04", "version": "0.1.2",
              "publication_state": "not_published", "source": source_files(),
              "runs": runs, "accepted_parent_raw_count": 22, "child_raw_count": 10,
              "independent_verdict": {"decision": independent["decision"],
                                      "sha256": sha(HERE / "review/independent-verdict.json")},
              "scope": "One native converter rejection of predefined <REPAIR> in a linked mission preparation TaskBreakDown.",
              "limits": "One negative preparation input; no successful physical simulation, GUI visual, cross-engine, all predefined-subtask legality, full B02.var04 or Issue18 claim.",
              "raw_location_policy": "local_only_ignored_runs_not_committed"}
    data = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    (HERE / "evidence-index.json").write_bytes(data)
    print(json.dumps({"index_sha256": hashlib.sha256(data).hexdigest(),
                      "source_files": len(result["source"]), "local_raw_count": 32}))


if __name__ == "__main__":
    main()
