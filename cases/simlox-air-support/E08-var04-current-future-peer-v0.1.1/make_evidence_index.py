"""Strict, read-only-by-default E08.var04 evidence-index builder.

Use --write-maps once after the author source and reviewer artifacts are final.
Use --write once after a deterministic dry build. Neither mode overwrites files.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import replay
import copy_excluded_source

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CASES = HERE.parent
CONTRACT = replay.CONTRACT
BASE = CONTRACT["base_commit"]
CONTRACT_SHA = "b95349ff646d5faaf2d754cce2624e39735bdf772865f294a93828140596bad3"
REVIEW = {
    "review/independent_contract_audit.py": "6c5b3d988cc60a322b56e223bf3a375ab07b782810501638b8ff125f54468202",
    "review/independent-contract-go-2026-10-07.md": "6bc9f3119405dd728fea8f2d13d857069d375b8ee038d097aa662af8420a5510",
    "review/independent_replay.py": "558993694997f82db32b8fd85598f3c251a2f304eac61dfaa27184c019a43dc7",
    "review/independent-verdict.json": "f75b63103a4d9d34e4fff73180f21a0957c0dfe24b5a8fdd6b0a1986cf3f47ad",
    "review/independent-postrun-review-2026-10-07.md": "f11d521d38874866e7d1b4b02ef8c1d923e5beea4a9e3fd24f1326e1dfcb5f75",
    "review/independent-author-probes-go-2026-10-07.md": "0543ea1c4e2a4477c6ad8f2807b917700ca3712aa2c6e24517c21c49f33378df",
    "review/independent-presentation-qualification-2026-10-07.md": "60da09c21aa8b052b84f9ad92a54c176c5a4e44bf88e66a55dd3f5d74e3dbb14",
}
AUTHOR = {
    "replay.py": "9cc22516d1fbd9fdee1f0b8c2e09980f57bfccba8e0421b00c492777c8b56ad7",
    "author-validation.json": "1746c334e2cc723903aa126bd4ec049e7f11181607a63d70e98ac8a72a5a882d",
    "self_check.py": "8c3e6a93e87e57363845678d59e0b3d84aa2551049a6c9e1968aaaaf3fe22ff6",
    "author-self-check.json": "1984b3fc8de8438acade1093add0033fff7bac997fd09e03813e3da7dd0c24f5",
    "self_check_v2.py": "7b991e0d76cde281930303d1693dda6597f753d8a9cfd13c050a72e8c225179c",
    "author-self-check-v2.json": "73a8648277530a8c36419a56d6cbf4e124680818fade0cbdd3f4981e553c8bf7",
}
RAW_MAP = HERE / "raw-custody-map.json"
CONTEXT_MAP = HERE / "context-custody-map.json"
CONTEXT_DIR = HERE / "preserved-root-context"
EXCLUDED_SOURCE_MAP = HERE / "excluded-source-custody-map.json"


def identity(path: Path) -> dict:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def check(path: Path, expected: dict) -> None:
    assert identity(path) == {"bytes": expected["bytes"], "sha256": expected["sha256"]}, str(path)


def encoded(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode("utf-8")


def load(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def relative(path: Path) -> str:
    return os.path.relpath(path, HERE).replace("\\", "/")


def gate() -> None:
    assert identity(HERE / "contract.json")["sha256"] == CONTRACT_SHA
    for name, sha in {**REVIEW, **AUTHOR}.items():
        assert identity(HERE / name)["sha256"] == sha, name
    assert replay.verify_all_pins() == 303
    author = load(HERE / "author-validation.json")
    assert author["decision"] == "AUTHOR_PASS_PENDING_INDEPENDENT"
    assert author["report_cells_checked"] == 48684 and author["source_pin_checks"] == 303
    expanded = load(HERE / "author-self-check-v2.json")
    assert expanded["decision"] == "PASS" and expanded["semantic_rejections"] == 24
    independent = load(HERE / "review/independent-verdict.json")
    assert independent["decision"] == "GO_BOUNDED"
    assert independent["full_expected_report_cells"] == 48684
    assert independent["direct_arms"] == 2 and independent["selected_station_reports"] == 6
    assert independent["script_sha256"] == REVIEW["review/independent_replay.py"]
    for script, expected in (("replay.py", author),
                             ("self_check_v2.py", expanded),
                             ("review/independent_replay.py", independent)):
        result = subprocess.run([sys.executable, "-X", "utf8", "-B", str(HERE / script)],
                                cwd=ROOT, check=True, capture_output=True, text=True, encoding="utf-8")
        assert json.loads(result.stdout) == expected, script


def raw_records() -> list[dict]:
    records = []
    for parent in CONTRACT["accepted_parents"]:
        for run in parent["runs"]:
            for name, pin in sorted(run["files"].items()):
                path = replay.repo_path(run["local_run_directory"]) / name
                check(path, pin)
                records.append({"status": "accepted", "role": run["role"], "run_id": run["run_id"],
                                "original_path": str(path), "name": name, **pin})
        for selector in parent["station_selectors"]:
            path = replay.repo_path(selector["path"])
            pin = {"bytes": selector["bytes"], "sha256": selector["sha256"]}
            check(path, pin)
            records.append({"status": "accepted", "role": "station_selector", "run_id": None,
                            "original_path": str(path), "name": path.name, **pin})
    for history in CONTRACT["excluded_history"]:
        for run in history["local_run_directories"]:
            for pin in run["files"]:
                path = replay.repo_path(pin["path"])
                check(path, pin)
                records.append({"status": "excluded_diagnostic", "role": history["package"],
                                "run_id": Path(run["directory"]).name, "original_path": str(path),
                                "name": path.name, "bytes": pin["bytes"], "sha256": pin["sha256"]})
    assert len(records) == 220 and len({x["original_path"] for x in records}) == 220
    assert sum(x["status"] == "accepted" for x in records) == 110
    return sorted(records, key=lambda x: x["original_path"])


def context_records() -> list[dict]:
    records = []
    for copy in sorted(CONTEXT_DIR.iterdir()):
        if not copy.is_file():
            continue
        original = ROOT / "tmp" / copy.name
        pin = identity(copy)
        if original.exists():
            check(original, pin)
        records.append({"original_path": str(original), "copy_path": relative(copy), **pin})
    assert len(records) == 11
    return records


def accepted_source_refs() -> list[dict]:
    records = []
    for parent in CONTRACT["accepted_parents"]:
        entries = parent["source_files"] + [parent["evidence_index"], parent["independent_verdict"], parent["signoff"]]
        for pin in entries:
            records.append(pin)
    for donor in CONTRACT["schema_dependencies"]:
        records.extend(donor[k] for k in ("accepted_source", "evidence_index", "signoff"))
    assert len(records) == 49
    out = []
    for pin in records:
        replay.verify_pin(pin)
        out.append({"path": relative(replay.repo_path(pin["path"])),
                    "local_disk": pin["local_disk"],
                    "published_git_at_base": pin["published_git_at_base"]})
    return sorted(out, key=lambda x: x["path"])


def sources() -> list[dict]:
    files = []
    for directory in (CASES / "E08-var04-current-future-peer-v0.1.0", HERE):
        assert directory.is_dir()
        for path in sorted(directory.rglob("*")):
            if not path.is_file() or any(part in ("runs", "__pycache__") for part in path.parts):
                continue
            if path == HERE / "evidence-index.json":
                continue
            if path.parent.name == "review" and path.name.startswith((
                    "independent-content-", "independent-publication-", "independent-staged-", "independent-remote-")):
                continue
            files.append({"path": relative(path), **identity(path)})
    assert len({x["path"] for x in files}) == len(files)
    return sorted(files, key=lambda x: x["path"])


def build() -> dict:
    gate()
    raw = raw_records()
    context = context_records()
    assert load(RAW_MAP) == raw and load(CONTEXT_MAP) == context
    excluded_source = copy_excluded_source.records()
    assert load(EXCLUDED_SOURCE_MAP) == excluded_source
    source = sources()
    return {
        "schema": "e08-var04-current-future-peer-evidence-index/v1",
        "case_id": "E08", "variant_id": "E08.var04", "version": "0.1.1",
        "publication_state": "reusable_published",
        "classification": "retrospective_source_bound_current_future_peer",
        "bounded_decision": "GO_BOUNDED_READONLY", "excluded_v010_decision": "NO_GO_CONTRACT",
        "new_native_runs": 0, "direct_arms": 2, "selected_station_reports": 6,
        "source_base_commit": BASE, "contract_sha256": CONTRACT_SHA,
        "independent_replay_sha256": REVIEW["review/independent_replay.py"],
        "independent_verdict_sha256": REVIEW["review/independent-verdict.json"],
        "report_cells_checked": 48684, "author_semantic_rejections": 24,
        "observed_cross_arm_cell_differences": 498,
        "accepted_run_record_count": 104, "accepted_station_selectors": 6,
        "excluded_diagnostic_run_records": 110,
        "raw_location_policy": "Original accepted and excluded run files and binary selectors remain ignored at exact mapped paths; restore SHA/size bytes, never synthesize or rerun. Root tmp receipts have named byte-identical package copies and cannot overwrite different existing bytes.",
        "scope": "Two sealed E08 direct arms with current peer stock versus scheduled future peer stock; full source/event-derived default and station report cells, typed item/transport ledgers and physical h10.8333 versus h15.5 aircraft recovery.",
        "limits": "Description, initial peer stock and scheduled transfer co-vary. No isolated timing/DLAYL effect, general priority, GUI visual, cross-engine or performance conclusion. Historical child PID/session unrecorded. No-wait WTS=null is bounded native presentation, not a general manual law.",
        "source_count": len(source), "source_files": source, "source": source,
        "accepted_source_refs": accepted_source_refs(),
        "raw_files": raw, "context_copies": context,
        "excluded_unpublished_source_copies": excluded_source,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-maps", action="store_true")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    assert not (args.write_maps and args.write)
    if args.write_maps:
        gate()
        for path, value in ((RAW_MAP, raw_records()), (CONTEXT_MAP, context_records())):
            assert not path.exists(), "never overwrite custody map: " + str(path)
            path.write_bytes(encoded(value))
        print(json.dumps({"raw_records": 220, "context_copies": 11, "written": True}, sort_keys=True))
        return
    index = build()
    data = encoded(index)
    target = HERE / "evidence-index.json"
    if target.exists():
        assert target.read_bytes() == data, "indexed source/raw bytes changed"
    if args.write:
        assert not target.exists(), "never overwrite a frozen index"
        target.write_bytes(data)
    print(json.dumps({"source_count": index["source_count"], "raw_records": len(index["raw_files"]),
                      "excluded_source_copies": len(index["excluded_unpublished_source_copies"]),
                      "accepted_source_refs": len(index["accepted_source_refs"]),
                      "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(),
                      "written": args.write}, sort_keys=True))


if __name__ == "__main__":
    main()
