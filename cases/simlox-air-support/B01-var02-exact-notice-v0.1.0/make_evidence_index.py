"""Seal the bounded B01 exact-notice child and accepted local dependencies."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUN_ID = "b01-var02-exact-notice-v010-ssh-20261006-01"
RAW_A01 = Path("C:/Users/user/Documents/Codex/2026-09-27/simlox-case-library-a01-a02-v1/repo/data/local/simlox-case-library/v1/A01")
EXCLUDE = {"evidence-index.json", "cli-scope-signoff-2026-10-06.md",
           "independent-publication-review-2026-10-06.md"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def pin(path):
    return {"bytes": path.stat().st_size, "sha256": sha(path)}


def check(path, expected):
    assert path.is_file() and sha(path) == expected, (path, expected)


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
    for key, name in (("input", "native-input.json"), ("contract", "contract.json"),
                      ("source_diff", "parent-diff.json"), ("evidence", "evidence-2026-09-29.md"),
                      ("independent_verdict", "review/independent-readonly-rerun-2026-09-29.json")):
        check(folder / name, entry[f"{key}_sha256"])
    run = Path(entry["local_run_dir"])
    check(run / "closure.json", entry["closure_sha256"])
    closure = load(run / "closure.json")
    assert closure["run_id"] == entry["run_id"] and len(closure["raw"]) == 11
    for name, artifact in closure["raw"].items():
        assert pin(run / name) == artifact, name
    return {"role": "accepted_b01", "run_id": entry["run_id"],
            "local_run_dir": str(run), "closure": pin(run / "closure.json"),
            "raw": closure["raw"]}


def accepted_a01(entry):
    folder = ROOT / entry["package"]
    for key, name in (("input", "native-input.json"), ("contract", "contract.json"),
                      ("signoff", "cli-scope-signoff-2026-09-29.md"),
                      ("evidence_index", "evidence-index.json")):
        check(folder / name, entry[f"{key}_sha256"])
    index = load(folder / "evidence-index.json")
    expected = {entry["final_run_id"]: entry["final_closure_sha256"],
                entry["replay_run_id"]: entry["replay_closure_sha256"]}
    assert len(index["runs"]) == 2
    result = []
    for run in index["runs"]:
        assert run["run_id"] in expected and len(run["artifacts"]) == 17
        for artifact in run["artifacts"].values():
            path = Path(artifact["path"])
            assert pin(path) == {"bytes": artifact["bytes"], "sha256": artifact["sha256"]}, path
        check(RAW_A01 / run["run_id"] / "closure.json", expected[run["run_id"]])
        result.append({"role": "accepted_a01", "run_id": run["run_id"],
                       "local_run_dir": run["directory"], "artifacts": run["artifacts"]})
    assert {x["run_id"] for x in result} == set(expected)
    return result


def child():
    run = HERE / "runs" / RUN_ID
    closure = load(run / "closure.json")
    assert closure["run_id"] == RUN_ID and closure["error"] is None
    assert closure["source_hashes_before"] == closure["source_hashes_after"]
    assert closure["invocation_sha256"] == sha(run / "invocation.json")
    assert len(closure["raw"]) == 12
    for name, artifact in closure["raw"].items():
        assert pin(run / name) == artifact, name
    return {"role": "bounded_b01_exact_notice_child", "run_id": RUN_ID,
            "local_run_dir": str(run.resolve()), "closure": pin(run / "closure.json"),
            "invocation": pin(run / "invocation.json"), "raw": closure["raw"]}


def main():
    contract = load(HERE / "contract.json")
    assert contract["version"] == "0.1.0-contract-candidate"
    author = load(HERE / "review/author-validation.json")
    independent = load(HERE / "review/independent-verdict.json")
    assert author["passed"] is True and author["checks_count"] == 4170 and not author["failed"]
    assert independent["decision"] == "GO_BOUNDED" and not independent["failures"]
    count = independent.get("checks", independent.get("checks_count"))
    assert isinstance(count, int) and count > 4000
    runs = accepted_a01(contract["prerequisite_a01"])
    runs.append(accepted_b01(contract["accepted_parent"]))
    runs.append(child())
    result = {"schema": "simlox-b01-var02-exact-notice-evidence-index/v1",
              "case_id": "B01", "variant_id": "B01.var02", "version": "0.1.0",
              "status": "bounded_exact_notice_ready_for_publication", "publication_state": "not_published",
              "source": source_files(), "accepted_parent": contract["accepted_parent"],
              "prerequisite_a01": contract["prerequisite_a01"], "runs": runs,
              "accepted_a01_raw_count": 34, "accepted_b01_raw_count": 11,
              "child_raw_count": 12, "author_checks": author["checks_count"],
              "independent_checks": count,
              "independent_verdict": {"decision": independent["decision"],
                                      "sha256": sha(HERE / "review/independent-verdict.json")},
              "scope": "One fixed B01 preparation with exact NOPER0.5 boundary and complete report field reconciliation.",
              "limits": "One seed, aircraft and preparation task; insufficient notice, GUI visual, cross-engine, performance, full B01.var02 and Issue18 remain unverified.",
              "raw_location_policy": "local_only_ignored_runs_not_committed"}
    data = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    (HERE / "evidence-index.json").write_bytes(data)
    print(json.dumps({"index_sha256": hashlib.sha256(data).hexdigest(),
                      "source_files": len(result["source"]), "local_raw_count": 57}))


if __name__ == "__main__":
    main()
