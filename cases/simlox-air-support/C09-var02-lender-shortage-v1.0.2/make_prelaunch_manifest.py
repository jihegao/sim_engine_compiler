"""Seal the complete v1.0.2 prelaunch byte inventory; no native invocation."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from verify_sources import verify as verify_sources

HERE = Path(__file__).resolve().parent
CONTRACT_SHA = "5433d55e26e06ededeb0fb3f714548ea98192b012f6de41ebb795930b624f236"
REVIEW_SHA = "3f89588e7be261480e1a7ea8cc6b2127fc8e84c2c0cd043651433b7078a55a95"
INPUT_SHA = {"ordinary": "b971efb41492789f32475aae7fa9f37c0e30e9461203b48d37e08e2747e8d2e3",
             "shortage": "fc65462d65c0fea1017f81e41dc283a9a1f666e7b1f42aeb262fc6f5b8384bff"}


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def path_of(value: str) -> Path:
    p = Path(value)
    return p if p.is_absolute() else (HERE / p).resolve()


def seal(path: Path, key: str) -> dict:
    raw = path.read_bytes()
    return {"key": key, "path": str(path.resolve()), "bytes": len(raw), "sha256": sha(raw)}


def referenced_paths(node: object):
    if isinstance(node, dict):
        if {"path", "local_disk", "published_git"} <= set(node):
            yield path_of(node["path"])
            return
        if {"path", "raw", "closure", "invocation"} <= set(node) and isinstance(node["raw"], (dict, list)):
            run = path_of(node["path"])
            for part, default in ((node["closure"], "closure.json"), (node["invocation"], "invocation.json")):
                yield path_of(part["path"]) if "path" in part else run / default
            raw = node["raw"].items() if isinstance(node["raw"], dict) else enumerate(node["raw"])
            for name, part in raw:
                yield path_of(part["path"]) if "path" in part else run / str(name)
            return
        for value in node.values():
            yield from referenced_paths(value)
    elif isinstance(node, list):
        for value in node:
            yield from referenced_paths(value)


def main() -> None:
    verified = verify_sources()
    assert verified["passed"]
    contract_path = HERE / "contract.json"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    assert sha(contract_path.read_bytes()) == CONTRACT_SHA
    local = {
        "child_contract": contract_path,
        "contract_review": HERE / "review/independent-contract-go-2026-10-07.md",
        "builder": HERE / "build.py",
        "ordinary_input": HERE / "ordinary-input.json",
        "shortage_input": HERE / "shortage-input.json",
        "exact_diff": HERE / "exact-diff.json",
        "roundtrip_checker": HERE / "check_roundtrip.py",
        "behavior_validator": HERE / "validate_native_cli.py",
        "report_oracle": HERE / "report_oracle.py",
        "source_verifier": HERE / "verify_sources.py",
        "static_negative_checks": HERE / "self_check.py",
        "runner_script": HERE / "run_native_ssh.ps1",
        "manifest_builder": HERE / "make_prelaunch_manifest.py",
        "prelaunch_readme": HERE / "README.md",
        "source_attributes": HERE / ".gitattributes",
        "source_ignore": HERE / ".gitignore",
        "v100_attributes": HERE.parent / "C09-var02-lender-shortage-v1.0.0/.gitattributes",
        "python_runtime": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
    }
    seen: set[Path] = set()
    records: list[dict] = []
    for key, path in local.items():
        path = path.resolve()
        assert path not in seen
        seen.add(path)
        records.append(seal(path, key))
    for path in referenced_paths(contract):
        path = path.resolve()
        if path not in seen:
            seen.add(path)
            records.append(seal(path, f"accepted_{len(records):03d}"))
    for value in contract["installed"].values():
        path = path_of(value["path"]).resolve()
        if path not in seen:
            seen.add(path)
            records.append(seal(path, f"installed_{len(records):03d}"))
    for value in contract["excluded_v100"]["records"].values():
        path = path_of(value["path"]).resolve()
        if path not in seen:
            seen.add(path)
            records.append(seal(path, f"excluded_{len(records):03d}"))
    excluded = contract["excluded_v101"]
    for key in ("manifest", "reproduction_guide", "independent_no_go", "accepted_boundary_calibration"):
        path = path_of(excluded[key]["path"]).resolve()
        if path not in seen:
            seen.add(path)
            records.append(seal(path, f"excluded_v101_{len(records):03d}"))
    for value in excluded["frozen_local_source_files"].values():
        path = path_of(value["path"]).resolve()
        if path not in seen:
            seen.add(path)
            records.append(seal(path, f"excluded_v101_{len(records):03d}"))
    by_key = {r["key"]: r for r in records}
    assert by_key["contract_review"]["sha256"] == REVIEW_SHA
    for arm in INPUT_SHA:
        assert by_key[f"{arm}_input"]["sha256"] == INPUT_SHA[arm]
    doc = {"schema": "c09-var02-v102-prelaunch-manifest/v1", "contract_sha256": CONTRACT_SHA,
           "run_ids": [contract["pair"]["arms"][a]["run_id"] for a in ("ordinary", "shortage")],
           "accepted_verification": verified["counts"], "source_files": records,
           "approval_path": str(HERE / "review/independent-prelaunch-go.json"),
           "purpose": "Exact source byte inventory before one guarded serial SSH0 native pair; no native call from this builder"}
    raw = (json.dumps(doc, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    path = HERE / "prelaunch-manifest.json"
    if path.exists():
        assert path.read_bytes() == raw, "frozen manifest differs"
    else:
        path.write_bytes(raw)
    print(json.dumps({"bytes": len(raw), "sha256": sha(raw), "source_count": len(records)}, sort_keys=True))


if __name__ == "__main__":
    main()
