"""Read-only evidence audit; --write requires exact independent GO pins."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess

from check_roundtrip import parse

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPO = HERE.parents[2]
CONTRACT_SHA = "5458f7b0615ecd8e25d1cba9fd25b14151297112c4446f29eb8bac3371ad31a3"
MANIFEST_SHA = "51cbf31e4222b07852857233f1f4cae402b551d9b8ef9c2bb9131e2ae4a72e0b"
APPROVAL_SHA = "9b600674b2edae53d7e9d096e1f4366f60df8bc13465de4be2d8b848995b3ed9"
CONTRACT_REVIEW_SHA = "a57a67110e5b0f84caf20009f32d6df61582341c8f74454c46a20f499373a010"
CLOSURE_SHA = {"joint": "5d03d8b0bda5d0d80d7d3a92fb6d5f32dc4099776d30f87ce0d036b9fb4ed402",
               "crewonly": "3363f3f8cf9f9cdd73460d76bd01e2a8608667856b1f90734a072b353a17482b"}
RUN_IDS = {arm: f"c02-var04-v100-{arm}-ssh-20261007-01" for arm in CLOSURE_SHA}
AUTHOR_CHECKS = {"joint": 5688, "crewonly": 5692}
INDEPENDENT_SCRIPT_SHA = "8997a142e768aedba1f54daf893796036696fa56fb1f8805a15fdbe86b5c9cca"
INDEPENDENT_VERDICT_SHA = "b3ebababf0630f4cbdc79adf3b2056956b11b0262601ef110763a6a9f2efbfb6"
INDEPENDENT_MEMO_SHA = "cffc909dc55f5e8c50a8cee68e983bbe0bda89bf5862c226351e1ca50f2dbe9f"
REJECTED_INDEX_SHA = "c825c2a0909912f10ebc7c387ce9631f47a1b3c3c401a13579d223b1307dbff1"
REJECTED_BUILDER_SHA = "76c6f1b3ef6daf6516106e8b36a721b2b008dca972bfc6aa9b7bf66a0c1fa50b"
REJECTED_SIGNOFF_SHA = "28516dc140eab81d2daa905de6312074166a5b06b9b1b73dc84252820f786022"
REJECTED_DIAGNOSTIC_SHA = "00558dc8a7bd17febeaa465842bb8ce33a6afe14139f684acd057d660f5660f6"
REJECTED_MEMO_SHA = "fa1de9280c9a6f99021683f458c1d62a9fc982689dcc84895fe7d3025df48548"


def pin(path: Path) -> dict:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def require(path: Path, digest: str) -> None:
    if len(digest) != 64 or pin(path)["sha256"] != digest:
        raise ValueError(f"exact byte pin differs: {path}")


def git_pin(path: Path) -> dict:
    raw = subprocess.run(["git", "show", "HEAD:" + path.relative_to(REPO).as_posix()],
                         cwd=REPO, capture_output=True, check=True).stdout
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def accepted_source(package: str, recorded: dict) -> dict:
    directory = ROOT / package
    tracked = subprocess.run(["git", "ls-files", "--", directory.relative_to(REPO).as_posix()],
                             cwd=REPO, capture_output=True, check=True, text=True).stdout.splitlines()
    actual = {str((REPO / name).relative_to(directory)).replace("\\", "/") for name in tracked}
    if actual != set(recorded):
        raise ValueError("accepted published file set differs: " + package)
    for name, value in recorded.items():
        path = directory / name
        if (pin(path) != {"bytes": value["local_bytes"], "sha256": value["local_sha256"]}
                or git_pin(path) != {"bytes": value["published_git_bytes"], "sha256": value["published_git_sha256"]}):
            raise ValueError("accepted local/Git byte pin differs: " + str(path))
    return {"package": package, "published_source": recorded}


def sealed_old_run(record: dict) -> dict:
    run = Path(record["path"])
    if pin(run / "closure.json") != record["closure"] or pin(run / "invocation.json") != record["invocation"]:
        raise ValueError("accepted closure/invocation differs: " + run.name)
    closure = read(run / "closure.json")
    if closure["run_id"] != record["run_id"] or closure["raw"] != record["raw"] or len(record["raw"]) != 11:
        raise ValueError("accepted closure raw map differs: " + run.name)
    if closure["invocation_sha256"] != record["invocation"]["sha256"]:
        raise ValueError("accepted invocation link differs: " + run.name)
    for name, value in record["raw"].items():
        if pin(run / name) != value:
            raise ValueError("accepted raw byte seal differs: " + run.name + "/" + name)
    return record


def sealed_child(arm: str, manifest: dict) -> dict:
    run = HERE / "runs" / RUN_IDS[arm]
    require(run / "closure.json", CLOSURE_SHA[arm])
    closure, invocation = read(run / "closure.json"), read(run / "invocation.json")
    if (closure["run_id"] != RUN_IDS[arm] or invocation["run_id"] != RUN_IDS[arm]
            or invocation["arm"] != arm or closure["error"] != "" or len(closure["raw"]) != 13
            or closure["invocation_sha256"] != pin(run / "invocation.json")["sha256"]):
        raise ValueError("child identity/closure differs: " + arm)
    expected = {item["key"]: item["sha256"] for item in manifest["source_files"]}
    if (closure["source_hashes_before"] != expected or closure["source_hashes_after"] != expected
            or invocation["source_hashes_before"] != expected):
        raise ValueError("child source before/after map differs: " + arm)
    if (invocation["manifest_sha256"] != MANIFEST_SHA or invocation["approval_sha256"] != APPROVAL_SHA
            or closure["manifest_sha256"] != MANIFEST_SHA or closure["approval_sha256"] != APPROVAL_SHA):
        raise ValueError("child manifest/approval link differs: " + arm)
    approval = read(HERE / "review" / "independent-prelaunch-go.json")
    preflight = HERE / approval["preflight_relative_path"]
    if (pin(preflight)["sha256"] != approval["preflight_sha256"]
            or invocation["approved_preflight_sha256"] != approval["preflight_sha256"]
            or closure["approved_preflight_sha256"] != approval["preflight_sha256"]):
        raise ValueError("approved preflight link differs: " + arm)
    for name, value in closure["raw"].items():
        if pin(run / name) != value:
            raise ValueError("child raw byte seal differs: " + arm + "/" + name)
    steps = read(run / "steps.json")
    if ([s["name"] for s in steps] != ["import", "export", "check_import_export", "calc", "jsonreport", "check_behavior"]
            or any(s["status"] != "completed" or s["exit_code"] != 0 or s["gui_preserved"] is not True for s in steps)):
        raise ValueError("child six-stage gate differs: " + arm)
    native = [s for s in steps if s["name"] in ("import", "export", "calc", "jsonreport")]
    if any(s["child_session_id"] != 0 or not isinstance(s["child_pid"], int) or s["child_pid"] <= 0 for s in native):
        raise ValueError("native child session/PID differs: " + arm)
    if len({s["child_pid"] for s in native}) != 4:
        raise ValueError("native PID reuse within run: " + arm)
    rt, author = read(run / "roundtrip-validation.json"), read(run / "author-validation.json")
    if rt.get("passed") is not True or rt.get("authored_row_tables") != 21:
        raise ValueError("21 row-containing roundtrip differs: " + arm)
    if (author.get("decision") != "GO_BOUNDED" or author.get("checks") != AUTHOR_CHECKS[arm]
            or author.get("passed") != AUTHOR_CHECKS[arm] or author.get("failures")):
        raise ValueError("author full-ledger result differs: " + arm)
    shape = {"ProblemDescription": (1, 1), "ResultSummary": (1, 11), "SystemResults": (72, 40),
             "StockTotalResults": (72, 16), "ResourceResults": (72, 16), "ResourceResultsTotal": (1, 14)}
    selected = {t["name"]: t for t in parse(run / "report-raw.json")["report"]["tables"]}
    if set(selected) != set(shape) or sum(a*b for a, b in shape.values()) != 5210:
        raise ValueError("six report tables differ: " + arm)
    for name, (count, width) in shape.items():
        rows = selected[name]["instances"][0]["rows"]
        if len(rows) != count or any(len(row) != width for row in rows):
            raise ValueError("report row/width differs: " + arm + "/" + name)
    return {"run_id": RUN_IDS[arm], "closure": pin(run / "closure.json"),
            "invocation": pin(run / "invocation.json"), "raw": closure["raw"],
            "raw_count": 13, "author_checks": AUTHOR_CHECKS[arm], "report_cells": 5210}


def include(path: Path) -> bool:
    rel = path.relative_to(HERE)
    return (path.is_file() and "runs" not in rel.parts and "__pycache__" not in rel.parts
            and path.suffix != ".pyc" and path.name != "evidence-index.json"
            and not path.name.startswith(("independent-publication-", "independent-staged-", "independent-remote-")))


def publication_repair() -> dict:
    preserved = {
        "review/excluded-staged-evidence-index.json": REJECTED_INDEX_SHA,
        "review/excluded-staged-make_evidence_index.py": REJECTED_BUILDER_SHA,
        "review/excluded-staged-cli-scope-signoff-2026-10-07.md": REJECTED_SIGNOFF_SHA,
        "review/excluded-staged-publication-diagnostic.json": REJECTED_DIAGNOSTIC_SHA,
        "review/independent-staged-no-go-2026-10-07.md": REJECTED_MEMO_SHA,
    }
    for name, digest in preserved.items():
        require(HERE / name, digest)
    diagnostic = read(HERE / "review/excluded-staged-publication-diagnostic.json")
    if (diagnostic["rejected_evidence_index_sha256"] != REJECTED_INDEX_SHA
            or diagnostic["independent_no_go"]["sha256"] != REJECTED_MEMO_SHA):
        raise ValueError("rejected publication diagnostic link differs")
    snapshots = diagnostic["rejected_root_index_snapshots"]
    for item in snapshots.values():
        path = Path(item["path"])
        if path.exists() and pin(path) != {"bytes": item["bytes"], "sha256": item["sha256"]}:
            raise ValueError("rejected root-index snapshot differs: " + str(path))
    return {"rejected_index": {"path": "review/excluded-staged-evidence-index.json", **pin(HERE / "review/excluded-staged-evidence-index.json")},
            "rejected_builder": {"path": "review/excluded-staged-make_evidence_index.py", **pin(HERE / "review/excluded-staged-make_evidence_index.py")},
            "rejected_signoff": {"path": "review/excluded-staged-cli-scope-signoff-2026-10-07.md", **pin(HERE / "review/excluded-staged-cli-scope-signoff-2026-10-07.md")},
            "diagnostic": {"path": "review/excluded-staged-publication-diagnostic.json", **pin(HERE / "review/excluded-staged-publication-diagnostic.json")},
            "independent_no_go": {"path": "review/independent-staged-no-go-2026-10-07.md", **pin(HERE / "review/independent-staged-no-go-2026-10-07.md")}}


def build(pre_independent: bool) -> dict:
    require(HERE / "contract.json", CONTRACT_SHA)
    require(HERE / "prelaunch-manifest.json", MANIFEST_SHA)
    require(HERE / "review" / "independent-contract-go-2026-10-07.md", CONTRACT_REVIEW_SHA)
    require(HERE / "review" / "independent-prelaunch-go.json", APPROVAL_SHA)
    contract, manifest = read(HERE / "contract.json"), read(HERE / "prelaunch-manifest.json")
    for item in manifest["source_files"]:
        if pin(Path(item["path"])) != {"bytes": item["bytes"], "sha256": item["sha256"]}:
            raise ValueError("frozen prelaunch source differs: " + item["key"])
    accepted = {}
    for case in ("C02", "C01"):
        record = contract["accepted_evidence"][case]
        accepted[case] = accepted_source(record["package"], record["published_source"])
        for key, value in record.items():
            if isinstance(value, dict) and "raw" in value:
                accepted[case][key] = sealed_old_run(value)
    children = {arm: sealed_child(arm, manifest) for arm in CLOSURE_SHA}
    repair = publication_repair()
    independent = None
    if not pre_independent:
        for name, digest in (("review/independent_replay.py", INDEPENDENT_SCRIPT_SHA),
                             ("review/independent-verdict.json", INDEPENDENT_VERDICT_SHA),
                             ("review/independent-postrun-review-2026-10-07.md", INDEPENDENT_MEMO_SHA)):
            require(HERE / name, digest)
        independent = read(HERE / "review" / "independent-verdict.json")
        if (independent.get("decision") != "GO_BOUNDED" or independent.get("checks") != 11405
                or independent.get("contract_sha256") != CONTRACT_SHA or independent.get("failures")
                or [r.get("run_id") for r in independent.get("runs", [])] != list(RUN_IDS.values())
                or [r.get("closure_sha256") for r in independent.get("runs", [])] != list(CLOSURE_SHA.values())):
            raise ValueError("independent postrun result is not GO")
    source = [{"path": p.relative_to(HERE).as_posix(), **pin(p)}
              for p in sorted(HERE.rglob("*")) if include(p)]
    return {"schema": "c02-var04-v100-evidence-index/v1", "case_id": "C02", "variant_id": "C02.var04",
            "version": "1.0.0", "publication_state": "not_published",
            "status": "pending_independent" if pre_independent else "bounded_native_evidence_ready_for_publication",
            "source": source, "prelaunch_manifest": {"path": "prelaunch-manifest.json", **pin(HERE / "prelaunch-manifest.json")},
            "rejected_staged_publication": repair,
            "prelaunch_approval": {"path": "review/independent-prelaunch-go.json", **pin(HERE / "review" / "independent-prelaunch-go.json")},
            "accepted": accepted, "new_native_runs": children, "accepted_raw_count": 33, "new_raw_count": 26,
            "author_checks": AUTHOR_CHECKS, "report_cells_per_arm": 5210, "independent": independent,
            "scope": "One fixed-seed one-aircraft explicit INSPECT subtask set; main E-GSE listed but omitted in crew-only arm.",
            "limits": "No general override, stochastic, other-task, GUI-only or cross-engine inference.",
            "raw_location_policy": "local_ignored_native_runs_not_committed"}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pre-independent", action="store_true", help="read-only available gates; never writes")
    parser.add_argument("--write", action="store_true", help="write only after exact independent GO pins are filled")
    args = parser.parse_args()
    if args.pre_independent and args.write:
        raise ValueError("pre-independent mode cannot write")
    result = build(args.pre_independent)
    if args.pre_independent:
        print(json.dumps({"status": result["status"], "source_count": len(result["source"]),
                          "accepted_raw_count": result["accepted_raw_count"], "new_raw_count": result["new_raw_count"]}))
        return
    data = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode()
    destination = HERE / "evidence-index.json"
    if args.write:
        if destination.exists():
            require(destination, REJECTED_INDEX_SHA)
        destination.write_bytes(data)
    elif not destination.exists() or destination.read_bytes() != data:
        raise ValueError("index absent/stale; exact independent GO and --write required")
    print(json.dumps({"index_sha256": hashlib.sha256(data).hexdigest(), "source_count": len(result["source"])}))


if __name__ == "__main__":
    main()
