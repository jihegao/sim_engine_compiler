"""Seal the bounded A02 same-time child and accepted local dependencies."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RAW_ROOT = Path("C:/Users/user/Documents/Codex/2026-09-27/simlox-case-library-a01-a02-v1/repo/data/local/simlox-case-library/v1")
EXCLUDE = {"evidence-index.json", "cli-scope-signoff-2026-10-06.md",
           "independent-publication-review-2026-10-06.md"}
RUN_ID = "a02-var03-same-time-v010-ssh-20261006-01"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def pin(path):
    return {"bytes": path.stat().st_size, "sha256": sha(path)}


def check(path, expected):
    assert path.is_file() and sha(path) == expected, (path, expected)


def sources():
    result = []
    for path in sorted(HERE.rglob("*")):
        if not path.is_file() or path.name in EXCLUDE or path.suffix == ".pyc":
            continue
        if "runs" in path.relative_to(HERE).parts or "__pycache__" in path.parts:
            continue
        result.append({"path": path.relative_to(HERE).as_posix(), **pin(path)})
    return result


def accepted(label, entry):
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
        check(RAW_ROOT / label / run["run_id"] / "closure.json", expected[run["run_id"]])
        result.append({"role": f"accepted_{label.lower()}", "run_id": run["run_id"],
                       "local_run_dir": run["directory"], "artifacts": run["artifacts"]})
    assert {x["run_id"] for x in result} == set(expected)
    return result


def analogue(entry):
    folder = ROOT / entry["package"]
    run = folder / "runs" / entry["run_id"]
    files = {"input": (folder / "native-input.json", "input_sha256"),
             "contract": (folder / "contract.json", "contract_sha256"),
             "signoff": (folder / "cli-scope-signoff-2026-10-06.md", "signoff_sha256"),
             "evidence_index": (folder / "evidence-index.json", "evidence_index_sha256"),
             "independent_verdict": (folder / "review/independent-verdict.json", "independent_verdict_sha256"),
             "closure": (run / "closure.json", "closure_sha256"),
             }
    for path, key in files.values():
        check(path, entry[key])
    closure = load(run / "closure.json")
    assert closure["run_id"] == entry["run_id"] and closure["error"] is None
    assert len(closure["raw"]) == 12
    for name, artifact in closure["raw"].items():
        assert pin(run / name) == artifact, name
    return {"role": "accepted_a02_var01_cancellation_analogue", "run_id": entry["run_id"],
            "local_run_dir": str(run.resolve()), "source_and_review":
            {name: pin(path) for name, (path, _) in files.items() if name != "closure"},
            "closure": pin(run / "closure.json"), "raw": closure["raw"]}


def child():
    run = HERE / "runs" / RUN_ID
    closure = load(run / "closure.json")
    assert closure["run_id"] == RUN_ID and closure["error"] is None
    assert closure["source_hashes_before"] == closure["source_hashes_after"]
    assert closure["invocation_sha256"] == sha(run / "invocation.json")
    assert len(closure["raw"]) == 12
    for name, artifact in closure["raw"].items():
        assert pin(run / name) == artifact, name
    return {"role": "bounded_a02_same_time_child", "run_id": RUN_ID,
            "local_run_dir": str(run.resolve()), "closure": pin(run / "closure.json"),
            "invocation": pin(run / "invocation.json"), "raw": closure["raw"]}


def main():
    contract = load(HERE / "contract.json")
    assert contract["version"] == "0.1.0-contract-candidate"
    author = load(HERE / "review/author-validation.json")
    independent = load(HERE / "review/independent-verdict.json")
    assert author["passed"] is True and author["checks_count"] == 4217 and not author["failed"]
    assert independent["decision"] == "GO_BOUNDED" and independent["checks"] == 4508 and not independent["failures"]
    runs = accepted("A01", contract["prerequisite_a01"]) + accepted("A02", contract["accepted_parent"])
    runs += [analogue(contract["accepted_cancellation_analogue"]), child()]
    value = {"schema": "simlox-a02-var03-same-time-v010-evidence-index/v1",
             "case_id": "A02", "variant_id": "A02.var03", "version": "0.1.0",
             "status": "bounded_same_time_ready_for_publication", "publication_state": "not_published",
             "source": sources(), "accepted_parent": contract["accepted_parent"],
             "prerequisite_a01": contract["prerequisite_a01"],
             "accepted_cancellation_analogue": contract["accepted_cancellation_analogue"],
             "runs": runs, "accepted_a01_a02_raw_count": 68, "cancellation_analogue_raw_count": 12,
             "child_raw_count": 12, "author_checks": author["checks_count"],
             "independent_checks": independent["checks"],
             "independent_verdict": {"decision": independent["decision"],
                                     "sha256": sha(HERE / "review/independent-verdict.json")},
             "scope": "One fixed A02 duplicate-key pair at h8 with one aircraft, one h8 winner, one h8.33333 cancellation, later h32 success and complete report reconciliation.",
             "limits": "One seed, aircraft and fixed mission profile; no generic tie-order rule, relational export, GUI visual, cross-engine or Issue18 completion claim.",
             "raw_location_policy": "local_only_ignored_runs_not_committed"}
    data = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    (HERE / "evidence-index.json").write_bytes(data)
    print(json.dumps({"index_sha256": hashlib.sha256(data).hexdigest(),
                      "source_files": len(value["source"]), "local_raw_count": 92}))


if __name__ == "__main__":
    main()
