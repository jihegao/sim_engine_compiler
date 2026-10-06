"""Seal B04.var02 v0.1.1 source, excluded v0.1.0, and local raw chain."""

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUN_ID = "b04-var02-turn-resource-v011-ssh-20261006-01"
EXPECTED = {
    "child": (HERE / "runs" / RUN_ID,
              "e9fb116596e60ad9d80d2c888c3c4f5c41543d44baee58130111082cc9b6e723", 13),
    "accepted_b04_var05": (ROOT / "B04-var05-turnround-breakdown-v0.1.0" / "runs" / "b04-var05-turnbreak-v010-ssh-20261006-01",
                           "58a4838596f96e07d5d20fff3cc4e02a7d3ef07f539d61f3a5c5caf0ca84b545", 13),
    "accepted_c01": (Path(r"C:\Users\user\dev\sim_engine_compiler-b02-v102\cases\simlox-air-support\C01-personnel-capacity-v1.0.2\runs\c01-v102-cap2-ssh-20260929-05"),
                     "770537c9097ba24fbec533d5c6f1eafa29153c18bde63cd0b1bc621a65c55163", 11),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pin(path):
    return {"bytes": path.stat().st_size, "sha256": sha(path)}


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def source_files():
    result = []
    for path in sorted(HERE.rglob("*")):
        if not path.is_file() or path.name == "evidence-index.json" or path.suffix == ".pyc":
            continue
        if "runs" in path.relative_to(HERE).parts or "__pycache__" in path.parts:
            continue
        result.append({"path": path.relative_to(HERE).as_posix(), **pin(path)})
    return result


def excluded_v010():
    directory = ROOT / "B04-var02-turnround-resource-v0.1.0"
    if (directory / "runs").exists():
        raise ValueError("excluded v0.1.0 unexpectedly has a native run directory")
    files = []
    for path in sorted(directory.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
            files.append({"path": path.relative_to(ROOT).as_posix(), **pin(path)})
    no_go = directory / "review" / "independent-prelaunch-no-go-2026-10-07.md"
    if sha(no_go) != "9ccf07faf96cdb1870c3b88a40071afa30e07f30346aef6dbad1455bbcc8a4ce":
        raise ValueError("excluded v0.1.0 NO_GO bytes differ")
    if sha(HERE / "review" / "excluded-v010-prelaunch-no-go-2026-10-07.md") != sha(no_go):
        raise ValueError("excluded NO_GO copy differs")
    return {"version": "0.1.0", "publication_state": "excluded_prelaunch_no_go",
            "native_process_started": False, "files": files,
            "no_go_sha256": sha(no_go)}


def sealed_run(role, directory, expected_sha, count):
    closure_path = directory / "closure.json"
    if sha(closure_path) != expected_sha:
        raise ValueError(f"{role} closure SHA differs")
    closure = load(closure_path)
    if closure["run_id"] != directory.name:
        raise ValueError(f"{role} run identity differs")
    raw = closure.get("raw", closure.get("artifacts", {}))
    if len(raw) != count:
        raise ValueError(f"{role} raw count differs: {len(raw)}")
    for name, seal in raw.items():
        path = Path(seal["path"]) if "path" in seal else directory / name
        if pin(path) != {"bytes": seal["bytes"], "sha256": seal["sha256"]}:
            raise ValueError(f"{role} raw seal differs: {name}")
    result = {"role": role, "run_id": directory.name, "local_run_dir": str(directory.resolve()),
              "closure": pin(closure_path), "raw": raw}
    if role == "child":
        if closure.get("error") is not None or closure["source_hashes_before"] != closure["source_hashes_after"]:
            raise ValueError("child closure error/source drift")
        invocation = directory / "invocation.json"
        if sha(invocation) != closure["invocation_sha256"]:
            raise ValueError("child invocation seal differs")
        result["invocation"] = pin(invocation)
    return result


def build():
    verdict = load(HERE / "review" / "independent-verdict.json")
    author = load(HERE / "runs" / RUN_ID / "author-validation.json")
    if verdict["decision"] != "GO_BOUNDED" or verdict["checks"] != 5753 or verdict["failures"]:
        raise ValueError("independent replay is not the accepted verdict")
    if author["decision"] != "GO_BOUNDED" or not author["passed"] or author["problems"]:
        raise ValueError("author gate is not accepted")
    runs = [sealed_run(role, *values) for role, values in EXPECTED.items()]
    return {
        "schema": "simlox-b04-var02-turnround-resource-evidence-index/v1",
        "case_id": "B04", "variant_id": "B04.var02", "version": "0.1.1",
        "status": "bounded_sufficient_turnround_resource_ready_for_publication",
        "publication_state": "not_published",
        "source": source_files(),
        "accepted_parent": {"package": "B04-var05-turnround-breakdown-v0.1.0",
                            "input_sha256": "965a3acc431696e56b760b07323e4cf11cb571e030885fff708787ce84f3e42f",
                            "closure_sha256": EXPECTED["accepted_b04_var05"][1],
                            "accepted_behavior": "two serial turnround subtasks, h23.5-24 and h26.75-27.25, with second launch h24.75"},
        "prerequisites": ["C01-personnel-capacity-v1.0.2", "B02 and A02 accepted via B04.var05"],
        "runs": runs,
        "excluded_attempt": excluded_v010(),
        "child_raw_count": 13, "accepted_raw_count": 24,
        "author_decision": "GO_BOUNDED", "independent_checks": verdict["checks"],
        "independent_verdict": {"decision": verdict["decision"],
                                "sha256": sha(HERE / "review" / "independent-verdict.json")},
        "report_cells_checked": verdict["parent_report_cells"] + verdict["resource_report_cells"],
        "scope": "One fixed-seed aircraft and two missions; one sufficient crew is requested and used for each first turnround subtask while flight and turnround timing match accepted B04.var05.",
        "limits": "No resource shortage, contention, shifts, item faults, other seeds, GUI visual, cross-engine, full B04.var02 or Issue18 claim.",
        "raw_location_policy": "local_only_ignored_runs_not_committed",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    data = (json.dumps(build(), ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    path = HERE / "evidence-index.json"
    if args.write:
        if path.exists():
            raise FileExistsError(path)
        path.write_bytes(data)
    elif path.read_bytes() != data:
        raise ValueError("frozen evidence index differs")
    print(json.dumps({"index_sha256": hashlib.sha256(data).hexdigest(),
                      "source_files": len(build()["source"]),
                      "excluded_source_files": len(build()["excluded_attempt"]["files"]),
                      "local_raw_count": 37}))


if __name__ == "__main__":
    main()
