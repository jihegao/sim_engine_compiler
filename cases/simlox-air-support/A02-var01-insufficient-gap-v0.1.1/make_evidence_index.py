"""Seal excluded prelaunch v0.1.0 and bounded insufficient-gap v0.1.1."""
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OLD = ROOT / "A02-var01-insufficient-gap-v0.1.0"
RAW_ROOT = Path("C:/Users/user/Documents/Codex/2026-09-27/simlox-case-library-a01-a02-v1/repo/data/local/simlox-case-library/v1")
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


def sources(folder):
    result = []
    for path in sorted(folder.rglob("*")):
        if not path.is_file() or path.name in EXCLUDE or path.suffix == ".pyc":
            continue
        if "runs" in path.relative_to(folder).parts or "__pycache__" in path.parts:
            continue
        result.append({"path": path.relative_to(folder).as_posix(), **pin(path)})
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


def sibling(entry):
    folder = ROOT / entry["package"]
    run = folder / "runs" / entry["run_id"]
    for key, path in (("input_sha256", folder / "native-input.json"),
                      ("evidence_index_sha256", folder / "evidence-index.json"),
                      ("independent_verdict_sha256", folder / "review/independent-verdict.json"),
                      ("closure_sha256", run / "closure.json")):
        check(path, entry[key])
    closure = load(run / "closure.json")
    assert closure["error"] is None and len(closure["raw"]) == 12
    for name, artifact in closure["raw"].items():
        assert pin(run / name) == artifact, name
    return {"role": "published_at_return_sibling", "run_id": entry["run_id"],
            "local_run_dir": str(run.resolve()), "closure": pin(run / "closure.json"),
            "raw": closure["raw"]}


def analogue(entry):
    folder = ROOT / entry["package"]
    run = folder / "runs" / entry["run_id"]
    files = {"input": (folder / entry["input_file"], "input_sha256"),
             "contract": (folder / "contract.json", "contract_sha256"),
             "signoff": (folder / "cli-scope-signoff-2026-09-30.md", "signoff_sha256"),
             "independent_verdict": (folder / "review/independent-priority-2026-09-30.json", "independent_verdict_sha256"),
             "closure": (run / "closure.json", "closure_sha256"),
             "model.log": (run / "model.log", "model_log_sha256"),
             "report-raw.json": (run / "report-raw.json", "report_raw_sha256")}
    for path, key in files.values():
        check(path, entry[key])
    return {"role": "accepted_a12_cancellation_analogue", "run_id": entry["run_id"],
            "local_run_dir": str(run.resolve()), "source_and_review":
            {name: pin(path) for name, (path, _) in files.items() if name not in ("closure", "model.log", "report-raw.json")},
            "raw": {name: pin(files[name][0]) for name in ("closure", "model.log", "report-raw.json")}}


def child(run_id):
    run = HERE / "runs" / run_id
    closure = load(run / "closure.json")
    assert closure["run_id"] == run_id and closure["error"] is None
    assert closure["source_hashes_before"] == closure["source_hashes_after"]
    assert closure["invocation_sha256"] == sha(run / "invocation.json")
    assert len(closure["raw"]) == 12
    for name, artifact in closure["raw"].items():
        assert pin(run / name) == artifact, name
    return {"role": "bounded_insufficient_gap_child", "run_id": run_id,
            "local_run_dir": str(run.resolve()), "closure": pin(run / "closure.json"),
            "invocation": pin(run / "invocation.json"), "raw": closure["raw"]}


def write(path, value):
    data = (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def main():
    contract = load(HERE / "contract.json")
    assert contract["version"] == "0.1.1-contract-candidate"
    old = contract["excluded_prelaunch"]
    for key, name in (("contract_sha256", "contract.json"),
                      ("validator_sha256", "validate_native_cli.py"),
                      ("runner_sha256", "run_native_ssh.ps1"),
                      ("no_go_sha256", "review/independent-prelaunch-no-go-2026-10-06.md")):
        check(OLD / name, old[key])
    assert not (OLD / "runs/a02-var01-insufficient-gap-v010-ssh-20261006-01").exists()
    author = load(HERE / "review/author-native-validation-2026-10-06.json")
    independent = load(HERE / "review/independent-verdict.json")
    assert author["passed"] is True and author["checks_count"] == 4229 and not author["failed"]
    assert independent["decision"] == "GO_BOUNDED" and independent["checks"] > 0 and not independent["failures"]
    old_index = {"schema": "simlox-a02-var01-insufficient-gap-v010-excluded-index/v1",
                 "case_id": "A02", "variant_id": "A02.var01", "version": "0.1.0",
                 "status": "excluded_prelaunch_no_go", "publication_state": "excluded_not_accepted",
                 "source": sources(OLD), "native_run_created": False,
                 "contract_sha256": old["contract_sha256"], "runner_sha256": old["runner_sha256"],
                 "validator_sha256": old["validator_sha256"], "no_go_sha256": old["no_go_sha256"],
                 "reason": old["reason"]}
    old_sha = write(OLD / "evidence-index.json", old_index)
    runs = accepted("A01", contract["prerequisite_a01"]) + accepted("A02", contract["accepted_parent"])
    runs += [sibling(contract["published_at_return_sibling"]), analogue(contract["accepted_a12_cancellation_analogue"]),
             child("a02-var01-insufficient-gap-v011-ssh-20261006-01")]
    new_index = {"schema": "simlox-a02-var01-insufficient-gap-v011-evidence-index/v1",
                 "case_id": "A02", "variant_id": "A02.var01", "version": "0.1.1",
                 "status": "bounded_insufficient_gap_arm_ready_for_publication", "publication_state": "not_published",
                 "source": sources(HERE), "accepted_parent": contract["accepted_parent"],
                 "prerequisite_a01": contract["prerequisite_a01"],
                 "published_at_return_sibling": contract["published_at_return_sibling"],
                 "accepted_a12_cancellation_analogue": contract["accepted_a12_cancellation_analogue"],
                 "excluded_prelaunch": {**old, "evidence_index_sha256": old_sha},
                 "runs": runs, "accepted_a01_a02_raw_count": 68, "published_sibling_raw_count": 12,
                 "a12_analogue_raw_count": 3, "child_raw_count": 12,
                 "author_checks": author["checks_count"], "independent_checks": independent["checks"],
                 "independent_verdict": {"decision": independent["decision"],
                                         "sha256": sha(HERE / "review/independent-verdict.json")},
                 "scope": "Fixed one-aircraft A02 second STIM h20-to9.5, identity-specific cancellation before h10 first return, two successful sorties and full ledgers.",
                 "limits": "One seed and fixed mission profile; no generic cancellation timing, other A02.var01 arms, GUI visual, cross-engine or Issue18 claim.",
                 "raw_location_policy": "local_only_ignored_runs_not_committed"}
    new_sha = write(HERE / "evidence-index.json", new_index)
    print(json.dumps({"old_index_sha256": old_sha, "new_index_sha256": new_sha,
                      "old_source_files": len(old_index["source"]), "new_source_files": len(new_index["source"]),
                      "local_raw_count": 95}))


if __name__ == "__main__":
    main()
