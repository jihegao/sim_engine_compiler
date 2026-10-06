"""Seal the B04.var03 read-only classification and its reused accepted run."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
ACCEPTED = ROOT / "B04-var05-turnround-breakdown-v0.1.0"
RUN = ACCEPTED / "runs" / "b04-var05-turnbreak-v010-ssh-20261006-01"
ACCEPTED_INDEX_SHA = "0faf2ccbca734cec8b7cf79bec8ac7961e7b209240829299a14edbf21404afab"
ACCEPTED_INPUT_SHA = "965a3acc431696e56b760b07323e4cf11cb571e030885fff708787ce84f3e42f"
ACCEPTED_CLOSURE_SHA = "58a4838596f96e07d5d20fff3cc4e02a7d3ef07f539d61f3a5c5caf0ca84b545"
ACCEPTED_REPORT_SHA = "df1c6055ce7cd32dea0e02112ab752bc34ec2484311e7d0baa44b04910a1c87a"
ACCEPTED_VERDICT_SHA = "fe9deac260919c28a7b5ee410f22d798d7d562de5b764d35b28d208bd0947fff"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pin(path):
    return {"bytes": path.stat().st_size, "sha256": sha(path)}


def load(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def local_sources():
    files = []
    for path in sorted(HERE.rglob("*")):
        if path.is_file() and path.name != "evidence-index.json" and path.suffix != ".pyc" and "__pycache__" not in path.parts:
            files.append({"path": path.relative_to(HERE).as_posix(), **pin(path)})
    return files


def accepted_source_pins():
    index_path = ACCEPTED / "evidence-index.json"
    if sha(index_path) != ACCEPTED_INDEX_SHA:
        raise ValueError("accepted B04.var05 index SHA differs")
    index = load(index_path)
    if len(index["source"]) != 21:
        raise ValueError("accepted B04.var05 source count differs")
    for record in index["source"]:
        path = ACCEPTED / record["path"]
        if pin(path) != {"bytes": record["bytes"], "sha256": record["sha256"]}:
            raise ValueError(f"accepted B04.var05 disk source differs: {record['path']}")
        git_path = "cases/simlox-air-support/B04-var05-turnround-breakdown-v0.1.0/" + record["path"]
        blob = subprocess.run(["git", "show", "HEAD:" + git_path], check=True, capture_output=True).stdout
        if len(blob) != record["bytes"] or hashlib.sha256(blob).hexdigest() != record["sha256"]:
            raise ValueError(f"accepted B04.var05 Git source differs: {record['path']}")
    return {"package": ACCEPTED.name, "index": pin(index_path),
            "input": pin(ACCEPTED / "native-input.json"),
            "independent_verdict": pin(ACCEPTED / "review" / "independent-verdict.json"),
            "source_pin_count": 21}


def reused_run():
    path = RUN / "closure.json"
    if sha(path) != ACCEPTED_CLOSURE_SHA or sha(RUN / "report-raw.json") != ACCEPTED_REPORT_SHA:
        raise ValueError("accepted run closure/report SHA differs")
    closure = load(path)
    if closure.get("run_id") != RUN.name or closure.get("error") is not None:
        raise ValueError("accepted run identity/error differs")
    raw = closure.get("raw", {})
    if len(raw) != 13:
        raise ValueError("accepted run raw count differs")
    for name, seal in raw.items():
        if pin(RUN / name) != {"bytes": seal["bytes"], "sha256": seal["sha256"]}:
            raise ValueError(f"accepted run raw differs: {name}")
    invocation = RUN / "invocation.json"
    if sha(invocation) != closure["invocation_sha256"]:
        raise ValueError("accepted invocation seal differs")
    return {"role": "reused_accepted_b04_var05", "run_id": RUN.name,
            "local_run_dir": str(RUN.resolve()), "closure": pin(path),
            "invocation": pin(invocation), "raw": raw}


def build():
    verdict = load(HERE / "review" / "independent-verdict.json")
    author = load(HERE / "author-validation.json")
    if (verdict.get("decision") != "GO_BOUNDED" or verdict.get("checks_passed") != 4162 or
            verdict.get("checks_total") != 4162 or verdict.get("failures") or verdict.get("report_cells") != 4044):
        raise ValueError("independent B04.var03 replay differs")
    if author.get("decision") != "GO_BOUNDED" or not author.get("passed") or author.get("problems"):
        raise ValueError("author B04.var03 checker differs")
    accepted = accepted_source_pins()
    if accepted["input"]["sha256"] != ACCEPTED_INPUT_SHA or accepted["independent_verdict"]["sha256"] != ACCEPTED_VERDICT_SHA:
        raise ValueError("accepted source/review SHA differs")
    run = reused_run()
    return {
        "schema": "simlox-b04-var03-notice-during-turnround-evidence-index/v1",
        "case_id": "B04", "variant_id": "B04.var03", "version": "0.1.0",
        "status": "bounded_read_only_notice_reclassification_ready_for_publication",
        "publication_state": "not_published", "new_native_run_count": 0,
        "source": local_sources(), "accepted_source": accepted,
        "runs": [run], "reused_raw_count": 13,
        "author_decision": author["decision"],
        "independent_verdict": {"decision": verdict["decision"], "checks": 4162,
                                "report_cells": 4044,
                                "sha256": sha(HERE / "review" / "independent-verdict.json")},
        "scope": "The same aircraft is preassigned to mission two at h23.75 during linked turnround h23.5-24, then physically allocated at h24 and launches h24.75.",
        "limits": "Retrospective reuse only: no new run, later-notice control, general lead time or same-time priority, GUI visual, cross-engine, full B04.var03 or Issue18 claim.",
        "raw_location_policy": "accepted_local_only_ignored_run_not_committed",
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
                      "accepted_source_pins": 21, "reused_raw_count": 13,
                      "new_native_run_count": 0}))


if __name__ == "__main__":
    main()
