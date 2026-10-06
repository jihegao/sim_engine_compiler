"""Seal B01.var03 task-route source, excluded contract and local raw evidence."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OLD = ROOT / "B01-var03-task-route-v0.1.0"
RUN_ID = "b01-var03-task-route-v011-ssh-20261006-01"
PARENT_RUN = Path(
    "C:/Users/user/dev/sim_engine_compiler-b03-v102/cases/simlox-air-support/"
    "B03-explicit-cold-hot-v1.0.2/runs/b03-v102-ssh-20260929-02"
)
EXCLUDE = {
    "evidence-index.json", "cli-scope-signoff-2026-10-06.md",
    "independent-staged-go-2026-10-06.md",
    "independent-remote-pr492-2026-10-06.md",
}


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pin(path: Path) -> dict:
    return {"bytes": path.stat().st_size, "sha256": sha(path)}


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def source_files() -> list[dict]:
    result = []
    for folder in (OLD, HERE):
        for path in sorted(folder.rglob("*")):
            if not path.is_file() or path.name in EXCLUDE or path.suffix == ".pyc":
                continue
            if "runs" in path.relative_to(folder).parts or "__pycache__" in path.parts:
                continue
            result.append({"path": Path(os.path.relpath(path, HERE)).as_posix(), **pin(path)})
    return sorted(result, key=lambda row: row["path"])


def sealed_run(role: str, folder: Path, closure_sha: str, run_id: str,
               input_sha: str, raw_count: int) -> dict:
    closure_path = folder / "closure.json"
    assert sha(closure_path) == closure_sha, role
    closure = load(closure_path)
    assert closure["run_id"] == run_id and not closure.get("error")
    if "input_sha256" in closure:
        assert closure["input_sha256"] == input_sha
    else:
        assert sha(folder / "input.json") == input_sha
    assert len(closure["raw"]) == raw_count, role
    assert closure["invocation_sha256"] == sha(folder / "invocation.json")
    for name, expected in closure["raw"].items():
        assert pin(folder / name) == expected, (role, name)
    return {
        "role": role, "run_id": run_id, "local_run_dir": str(folder.resolve()),
        "closure": pin(closure_path), "invocation": pin(folder / "invocation.json"),
        "raw": closure["raw"],
    }


def main() -> None:
    contract = load(HERE / "contract.json")
    assert contract["version"] == "0.1.1-contract-candidate"
    assert contract["ownership"]["native_run_id_reserved"] == RUN_ID
    assert sha(OLD / "contract.json") == "0432b529385d20f26d93ca7d75545e8d2490050a94b61286334cd68a52385ca9"
    assert sha(OLD / "review/independent-contract-nogo-2026-10-06.md") == "c4bd04d5132e126f7ee79fa1d1b8c4562e004b336395876744a6020109124ca7"
    parent = contract["accepted_parent"]
    for key, name in (
        ("input_sha256", "native-input.json"),
        ("contract_sha256", "contract.json"),
    ):
        assert sha(ROOT / parent["package"] / name) == parent[key], key
    assert sha(ROOT / "A02-single-aircraft-repeated-missions/cli-scope-signoff-2026-09-29.md") == contract["instructional_prerequisite"]["signed_scope_sha256"]
    author = load(HERE / "review/author-validation.json")
    independent = load(HERE / "review/independent-verdict-corrected-v2.json")
    first_pass = load(HERE / "review/independent-verdict-diagnostic-v1.json")
    assert author["decision"] == "GO_BOUNDED" and author["checks"] == 4537 and not author["failures"]
    assert independent["decision"] == "GO_BOUNDED" and independent["passed"] == independent["total"] == 4278 and not independent["failures"]
    assert first_pass["decision"] == "NO_GO" and first_pass["passed"] == 4276 and first_pass["total"] == 4278
    runs = [
        sealed_run("accepted_b03_parent", PARENT_RUN, parent["closure_sha256"],
                   parent["accepted_run_id"], parent["input_sha256"], 11),
        sealed_run("bounded_b01_var03_child", HERE / "runs" / RUN_ID,
                   "d06ece9686a3d088e456885fe1d8e17aa11e099d3f0636520f2b9c1f04d15c75",
                   RUN_ID, contract["source_delta"]["child_input_sha256"], 12),
    ]
    result = {
        "schema": "simlox-b01-var03-task-route-evidence-index/v1",
        "case_id": "B01", "variant_id": "B01.var03", "version": "0.1.1",
        "publication_state": "not_published", "source": source_files(),
        "excluded_contract": {
            "version": "0.1.0", "status": "NO_GO_CONTRACT", "native_run": "none",
            "contract": pin(OLD / "contract.json"),
            "independent_review": pin(OLD / "review/independent-contract-nogo-2026-10-06.md"),
        },
        "accepted_parent": parent,
        "instructional_prerequisite": contract["instructional_prerequisite"],
        "runs": runs,
        "accepted_parent_raw_count": 11, "child_raw_count": 12,
        "author_checks": author["checks"], "independent_checks": independent["total"],
        "independent_first_pass": {
            "status": "NO_GO_REVIEWER_CHECKER", "passed": first_pass["passed"],
            "total": first_pass["total"],
            "script": pin(HERE / "review/independent_replay_diagnostic_v1.py"),
            "verdict": pin(HERE / "review/independent-verdict-diagnostic-v1.json"),
        },
        "independent_corrected": {
            "decision": independent["decision"],
            "script": pin(HERE / "review/independent_replay_corrected_v2.py"),
            "verdict": pin(HERE / "review/independent-verdict-corrected-v2.json"),
        },
        "scope": "One fixed-seed B01.var03 task-route arm: explicit HOT-SORTIE selection at h8, accepted hot routes at h12/h16.",
        "limits": "No automatic history switching, aircraft/site mapping, resources, fault, GUI visual, cross-engine, full B01.var03 or Issue18 claim.",
        "raw_location_policy": "local_only_ignored_runs_not_committed",
    }
    data = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    (HERE / "evidence-index.json").write_bytes(data)
    print(json.dumps({
        "index_sha256": hashlib.sha256(data).hexdigest(),
        "source_files": len(result["source"]),
        "local_raw_count": 23,
    }))


if __name__ == "__main__":
    main()
