"""Seal B04.var05 source and the accepted local raw evidence chain."""

import argparse
import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RUN_ID = "b04-var05-turnbreak-v010-ssh-20261006-01"
EXPECTED = {
    "child": (HERE / "runs" / RUN_ID,
              "58a4838596f96e07d5d20fff3cc4e02a7d3ef07f539d61f3a5c5caf0ca84b545", 13),
    "accepted_b04": (ROOT / "B04-cross-midnight-turnround-v1.0.1" / "runs" / "b04-v101-turnround-20260930-01",
                     "85d25bd8fa2a053639ca9a93b3bbdd78a5c04e3db9a5d826e27998d500f95ae1", 12),
    "accepted_b02": (Path(r"C:\Users\user\dev\sim_engine_compiler-b02-v102\cases\simlox-air-support\B02-serial-preparation-v1.0.2\runs\b02-v102-ssh-20260929-01"),
                     "3bbaffe3460da2195a4084cb3b92e1fc9c605a5d01380619abf92e3cd107f570", 11),
    "accepted_a02_final": (Path(r"C:\Users\user\Documents\Codex\2026-09-27\simlox-case-library-a01-a02-v1\repo\data\local\simlox-case-library\v1\A02\a02-bound-final-20260927-03"),
                           "fc0cc2d0578d2e8d126e79886ab2ba72238a725aea86c361ede6d48dadc6a69a", 12),
    "accepted_a02_replay": (Path(r"C:\Users\user\Documents\Codex\2026-09-27\simlox-case-library-a01-a02-v1\repo\data\local\simlox-case-library\v1\A02\a02-bound-replay-20260927-04"),
                            "9a44bc9f5d52cfd2178545315b6cd9b380585e98c36502025b329e380f1909d1", 12),
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
    if verdict["decision"] != "GO_BOUNDED" or verdict["checks"] != 4595 or verdict["failures"]:
        raise ValueError("independent replay is not the accepted verdict")
    if author["decision"] != "GO_BOUNDED" or not author["passed"] or author["problems"]:
        raise ValueError("author gate is not accepted")
    runs = [sealed_run(role, *values) for role, values in EXPECTED.items()]
    return {
        "schema": "simlox-b04-var05-turnround-breakdown-evidence-index/v1",
        "case_id": "B04", "variant_id": "B04.var05", "version": "0.1.0",
        "status": "bounded_turnround_breakdown_ready_for_publication",
        "publication_state": "not_published",
        "source": source_files(),
        "accepted_parent": {"package": "B04-cross-midnight-turnround-v1.0.1",
                            "input_sha256": "9f985c071d7d1958b55659f8ae39bc4c47580847d3bf6057d5e01f483004a9c5",
                            "closure_sha256": EXPECTED["accepted_b04"][1],
                            "accepted_behavior": "one-hour scalar turnround after each mission, with second launch delayed to h25"},
        "prerequisites": ["B02-serial-preparation-v1.0.2", "A02 accepted repeated-mission final/replay"],
        "runs": runs,
        "child_raw_count": 13, "accepted_raw_count": 47,
        "author_decision": "GO_BOUNDED", "independent_checks": verdict["checks"],
        "independent_verdict": {"decision": verdict["decision"],
                                "sha256": sha(HERE / "review" / "independent-verdict.json")},
        "report_cells_checked": verdict["report_cells_checked"],
        "scope": "One fixed-seed aircraft, two missions and a linked custom two-step turnround replacing a one-hour scalar with a half-hour strict sequence; second launch h24.75.",
        "limits": "No resource competition, item faults, other seeds, general turnround rule, GUI visual, cross-engine, full B04.var05 or Issue18 claim.",
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
                      "source_files": len(build()["source"]), "local_raw_count": 60}))


if __name__ == "__main__":
    main()
