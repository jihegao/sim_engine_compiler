"""Seal B04.var02 zero-crew v0.1.3 source, excluded v0.1.2, and local raw chain."""

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUN_ID = "b04-var02-zero-crew-v013-ssh-20261007-01"
EXPECTED = {
    "child": (HERE / "runs" / RUN_ID,
              "aaa61f92f7a675361ba6e16d6fb4e92cbd2b1a0b179349f30cbc4e3a32e773ca", 13),
    "accepted_b04_var02": (ROOT / "B04-var02-turnround-resource-v0.1.1" / "runs" /
                           "b04-var02-turn-resource-v011-ssh-20261006-01",
                           "e9fb116596e60ad9d80d2c888c3c4f5c41543d44baee58130111082cc9b6e723", 13),
    "accepted_c01_capacity_zero": (
        Path(r"C:\Users\user\dev\sim_engine_compiler-b02-v102\cases\simlox-air-support\C01-personnel-capacity-v1.0.2\runs\c01-v102-cap0-ssh-20260929-03"),
        "722e9eab571f8a7bc32aa593fe8782b30cc182a4a196b93f0f559129f85f4dcd", 11),
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pin(path):
    return {"bytes": path.stat().st_size, "sha256": sha(path)}


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def source_files():
    files = []
    for path in sorted(HERE.rglob("*")):
        if not path.is_file() or path.name == "evidence-index.json" or path.suffix == ".pyc":
            continue
        if "runs" in path.relative_to(HERE).parts or "__pycache__" in path.parts:
            continue
        files.append({"path": path.relative_to(HERE).as_posix(), **pin(path)})
    return files


def excluded_v012():
    directory = ROOT / "B04-var02-zero-crew-v0.1.2"
    if (directory / "runs").exists():
        raise ValueError("excluded v0.1.2 unexpectedly has a native run directory")
    files = []
    for path in sorted(directory.rglob("*")):
        if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc":
            files.append({"path": path.relative_to(ROOT).as_posix(), **pin(path)})
    no_go = directory / "review" / "independent-prelaunch-no-go-2026-10-07.md"
    if sha(no_go) != "699044fd3b05cf9630f660b8c2977cc4662015c483d31bc3f047478d21a606af":
        raise ValueError("excluded v0.1.2 NO_GO bytes differ")
    return {"version": "0.1.2", "publication_state": "excluded_prelaunch_no_go",
            "native_process_started": False, "files": files, "no_go_sha256": sha(no_go)}


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
    b04 = verdict.get("b04_checks", {})
    c01 = verdict.get("c01_supplemental_checks", {})
    if (verdict.get("decision") != "GO_BOUNDED" or b04.get("passed") != 5633 or
            b04.get("total") != 5633 or b04.get("failures") or
            c01.get("passed") != 13 or c01.get("total") != 13 or c01.get("failures")):
        raise ValueError("independent replay is not the accepted verdict")
    if author["decision"] != "GO_BOUNDED" or not author["passed"] or author["problems"]:
        raise ValueError("author gate is not accepted")
    runs = [sealed_run(role, *values) for role, values in EXPECTED.items()]
    return {
        "schema": "simlox-b04-var02-zero-crew-evidence-index/v1",
        "case_id": "B04", "variant_id": "B04.var02", "version": "0.1.3",
        "status": "bounded_zero_turnround_crew_ready_for_publication",
        "publication_state": "not_published", "source": source_files(),
        "accepted_parent": {"package": "B04-var02-turnround-resource-v0.1.1",
                            "input_sha256": "0d799bc6b2d4f8184db0bc33ddbffcaa51a822478b746fab3d4be9d942ee34d5",
                            "closure_sha256": EXPECTED["accepted_b04_var02"][1],
                            "accepted_behavior": "one P-CREW enables each turnround; it is booked only for INSPECT, while SERVICE is unresourced; both missions launch and succeed"},
        "prerequisites": ["C01-personnel-capacity-v1.0.2", "B04.var02 sufficient-resource parent"],
        "runs": runs, "excluded_attempt": excluded_v012(),
        "child_raw_count": 13, "accepted_raw_count": 24,
        "author_decision": "GO_BOUNDED", "independent_checks": 5633,
        "c01_supplemental_checks": 13,
        "independent_verdict": {"decision": verdict["decision"],
                                "sha256": sha(HERE / "review" / "independent-verdict.json")},
        "report_cells_checked": 5210,
        "scope": "One fixed-seed aircraft and two missions; zero available P-CREW leaves the first turnround waiting, while the second mission cancels at observed h25 without launch.",
        "limits": "No general deadline, partial booking, substitution, shifts, competition, GUI visual, cross-engine, full B04.var02 or Issue18 claim.",
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
