"""Freeze exact prelaunch source bytes; never include a mutable approval or run."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
OUT = HERE / "prelaunch-manifest.json"
OWNED = [
    ".gitattributes", ".gitignore", "contract.json", "README.md", "REPRODUCTION.md", "build.py",
    "shortage-input.json", "exact-diff.json", "check_roundtrip.py",
    "verify_sources.py", "physical_ledger.py", "report_oracle.py",
    "numeric_bounds.py", "validate_native_cli.py", "self_check.py",
    "run_native_ssh.ps1", "preflight_receipt.ps1", "test_preflight_receipt.ps1",
    "captured_process.ps1", "test_captured_process.ps1",
    "checker_receipt.ps1", "test_checker_receipt.ps1",
    "preserved-prefreeze/captured_process-first-draft.ps1",
    "preserved-prefreeze/test_captured_process-first-draft.ps1",
    "make_prelaunch_manifest.py",
    "review/independent-contract-go-2026-10-07.md",
    "review/independent_contract_pin_audit.py",
    "review/independent-helper-test-go-2026-10-07.md",
    "review/independent-helper-ssh-go-2026-10-07.md",
    "review/captured-process-test-ssh0-20261007T071542425Z.json",
]


def seal(path: Path) -> dict:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def candidate() -> dict:
    contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
    assert contract["schema"] == "simlox-c09-var02-lender-shortage-v107-child-contract/v1"
    assert contract["planned_child"]["run_id"] == "c09-var02-v107-shortage-ssh-20261007-01"
    result = []
    keys = set()
    def add(key: str, path: Path, pin: dict | None = None) -> None:
        path = path.resolve()
        assert key not in keys and path.is_file(), (key, path)
        keys.add(key)
        identity = seal(path)
        if pin is not None:
            assert identity == {"bytes": pin["bytes"], "sha256": pin["sha256"]}, key
        result.append({"key": key, "path": str(path), **identity})
    archive = HERE / "preserved-root-context"
    owned = OWNED + [p.relative_to(HERE).as_posix() for p in sorted(archive.rglob("*")) if p.is_file()]
    for name in owned:
        add({"contract.json": "child_contract", "shortage-input.json": "shortage_input",
             "validate_native_cli.py": "behavior_validator", "run_native_ssh.ps1": "runner_script"}.get(name, "owned:" + name), HERE / name)
    def pins(node: object, prefix: str) -> None:
        if isinstance(node, dict):
            if {"path", "bytes", "sha256"} <= set(node):
                path = Path(node["path"])
                add(prefix, path if path.is_absolute() else HERE / path, node)
                return
            for key, value in node.items():
                pins(value, prefix + "/" + str(key))
        elif isinstance(node, list):
            for i, value in enumerate(node):
                pins(value, prefix + "/" + str(i))
    pins(contract, "contract_pin")
    helper_custody = json.loads((archive / "actual-ssh5-helper-test-custody.json").read_text(encoding="utf-8"))
    receipt_pin = helper_custody["receipt_identity"]
    add("helper_test_original_receipt", Path(helper_custody["receipt_original"]), receipt_pin)
    for i, rec in enumerate(helper_custody["raw"]):
        add(f"helper_test_original_raw:{i}", Path(rec["original_path"]), rec)
    for name in ("c09-var02-v107-helper-test-freeze-20261007.json",
                 "c09-var02-v107-helper-test-transport-20261007T071542425Z.txt"):
        original = HERE.parents[2] / "tmp" / name
        copy = archive / name
        add("helper_test_original_context:" + name, original, seal(copy))
    for version, expected in (("excluded_v105", 384), ("excluded_v106", 809)):
        prior_manifest_pin = contract[version]["manifest"]
        prior_manifest_path = (HERE / prior_manifest_pin["path"]).resolve()
        prior_manifest = json.loads(prior_manifest_path.read_text(encoding="utf-8"))
        assert len(prior_manifest["source_files"]) == expected
        for i, rec in enumerate(prior_manifest["source_files"]):
            add(f"{version}_source:{i}", Path(rec["path"]), rec)
    parent_index_pin = contract["published_parent"]["evidence_index"]
    parent_index_path = (HERE / parent_index_pin["path"]).resolve()
    parent_index = json.loads(parent_index_path.read_text(encoding="utf-8"))
    assert len(parent_index["source_files"]) == 101
    assert len(parent_index["raw_files"]) == 130
    assert len(parent_index["accepted_source_refs"]) == 77
    for i, rec in enumerate(parent_index["source_files"]):
        add(f"parent_source:{i}", parent_index_path.parent / rec["path"], rec)
    for i, rec in enumerate(parent_index["raw_files"]):
        add(f"parent_raw:{i}", parent_index_path.parent / rec["path"], rec)
    for i, rec in enumerate(parent_index["accepted_source_refs"]):
        add(f"accepted_local:{i}", parent_index_path.parent / rec["path"], rec["local_disk"])
    custody_pin = contract["published_parent"]["raw_custody_map"]
    custody_path = (HERE / custody_pin["path"]).resolve()
    custody = json.loads(custody_path.read_text(encoding="utf-8"))
    for i, run in enumerate(custody["accepted_dependencies"] + [custody["sole_failed_ordinary"]]):
        for kind in ("closure", "invocation", "failure_seal"):
            if kind in run:
                rec = run[kind]
                add(f"custody:{i}:{kind}", custody_path.parent / rec["path"], rec)
    for version in ("1.0.3", "1.0.4"):
        add(f"excluded_attribute:{version}", HERE.parent / f"C09-var02-lender-shortage-v{version}" / ".gitattributes")
    return {"schema": "c09-var02-v107-prelaunch-manifest/v1",
            "contract_sha256": seal(HERE / "contract.json")["sha256"],
            "run_id": contract["planned_child"]["run_id"],
            "source_count": len(result), "source_files": result,
            "independent_replay_state": "excluded_mutable_review_method; fresh approval binds final reviewer SHA",
            "native_runs_authorized_by_manifest": 0}


def main() -> None:
    data = (json.dumps(candidate(), ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    if "--write" in sys.argv:
        assert not OUT.exists(), "a frozen manifest exists; preserve it before any versioned correction"
        OUT.write_bytes(data)
    else:
        assert OUT.is_file() and OUT.read_bytes() == data, "manifest source pin drift"
    print(json.dumps({"manifest_sha256": hashlib.sha256(data).hexdigest(),
                      "source_count": json.loads(data)["source_count"], "verified": True}, sort_keys=True))


if __name__ == "__main__":
    main()
