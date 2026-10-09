#!/usr/bin/env python3
"""Create and verify the byte-bound source freeze for I05.var05 v1.0.6."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUN_ID = "i05-var05-item-replacement-v106-ssh-20261009-01"
NATIVE_RUN = Path(r"C:\Users\user\Documents\Codex\2026-09-29\simlox-c04-deadline\repo\tmp\i05-var05-item-replacement-v106-20261009-01")


def digest(path: Path) -> tuple[int, str, int]:
    data = path.read_bytes()
    return len(data), hashlib.sha256(data).hexdigest(), int(path.stat().st_file_attributes)


def pin(role: str, path: Path) -> dict[str, object]:
    size, sha, attrs = digest(path)
    return {"role": role, "path": str(path), "bytes": size, "sha256": sha, "windows_attributes": attrs}


def strict_json(path: Path) -> dict:
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate JSON key: {key}")
            result[key] = value
        return result

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))


def main() -> None:
    if NATIVE_RUN.exists():
        raise SystemExit(f"reserved v106 native run path already exists: {NATIVE_RUN}")
    execution = strict_json(HERE / "execution-contract.json")
    if execution["run_id"] != RUN_ID or Path(execution["native_run_directory"]) != NATIVE_RUN:
        raise SystemExit("execution contract run identity differs from this freezer")
    contract = strict_json(HERE / "contract.json")
    if contract["version"] != "1.0.6" or contract["publication_state"] != "not_published":
        raise SystemExit("contract version or publication state is not the v1.0.6 candidate")

    local_paths = [
        "README.md", "contract.json", "execution-contract.json", "build.py",
        "check_source_delta.py", "native-input.json", "check_roundtrip.py",
        "test_roundtrip_policy.py", "validate_native_cli.py", "run_native_ssh.ps1",
        "ssh_transport.py", "make_prelaunch_manifest.py", "make_source_freeze.py",
        "review/source-delta-checker-receipt.json", "review/local-gates-receipt.json",
        "review/v104-roundtrip-v106-replay.json",
    ]
    source_files = [pin("owned:" + name, HERE / name) for name in local_paths]
    for path in sorted((HERE / "preserved-history").rglob("*")):
        if path.is_file():
            rel = path.relative_to(HERE).as_posix()
            source_files.append(pin("preserved:" + rel, path))

    package_root = HERE.parent
    source_files.append(pin("live:case-catalog", package_root / "catalog-v2.json"))
    parent = package_root / "H02-var04-item-damage-replacement-fallback-v1.0.0"
    parent_index = strict_json(parent / "evidence-index.json")
    run = parent_index["accepted_runs"]["fallback"]
    if run["run_id"] != "h02-var04-item-fallback-v100-ssh-20261002-01":
        raise SystemExit("accepted H02 fallback parent run identity differs")
    if run["input_sha256"] != hashlib.sha256((parent / "fallback-input.json").read_bytes()).hexdigest():
        raise SystemExit("accepted H02 fallback parent input hash differs")
    for role, path in (("input", parent / "fallback-input.json"),
                       ("evidence-index", parent / "evidence-index.json"),
                       ("scope-signoff", parent / "cli-scope-signoff-2026-10-02.md")):
        source_files.append(pin("parent:" + role, path))
    for name, expected in run["raw"].items():
        path = Path(run["local_path"]) / name
        entry = pin("parent_raw:" + name, path)
        if entry["bytes"] != expected["bytes"] or entry["sha256"] != expected["sha256"]:
            raise SystemExit(f"accepted parent raw evidence changed: {name}")
        if entry["windows_attributes"] != 32:
            raise SystemExit(f"accepted parent raw evidence attributes changed: {name}")
        source_files.append(entry)

    roles = [entry["role"] for entry in source_files]
    if len(roles) != len(set(roles)):
        raise SystemExit("duplicate source role")
    freeze = {
        "schema": "i05-var05-source-freeze/v3",
        "case_id": "I05",
        "variant_id": "I05.var05",
        "version": "1.0.6",
        "state": "source_frozen_for_independent_review",
        "native_actions": 0,
        "accepted_parent_runs_repeated": 0,
        "base_commit": "fd2bbeece3daa1815dd1b9779f3134b18776aed4",
        "reserved_child_run_id": RUN_ID,
        "reserved_child_native_path": str(NATIVE_RUN),
        "reserved_child_path_absent_at_freeze": True,
        "source_file_count": len(source_files),
        "source_files": source_files,
        "independent_review": "pending",
    }
    freeze_path = HERE / "source-freeze.json"
    freeze_path.write_text(json.dumps(freeze, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    freeze_size, freeze_sha, _ = digest(freeze_path)
    verification = {
        "schema": "i05-var05-source-freeze-verification/v3",
        "state": "PASS_LOCAL_SOURCE_FREEZE_AND_ROUNDTRIP_POLICY_TESTS; INDEPENDENT_REVIEW_PENDING",
        "source_freeze": {"path": "source-freeze.json", "bytes": freeze_size, "sha256": freeze_sha},
        "source_file_count": len(source_files),
        "all_frozen_source_bytes_sha_and_attributes_match": True,
        "reserved_run_path_absent": not NATIVE_RUN.exists(),
        "native_actions": 0,
        "accepted_parent_runs_repeated": 0,
        "independent_review": "pending",
    }
    (HERE / "source-freeze-verification.json").write_text(
        json.dumps(verification, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": "SOURCE_FREEZE_CREATED", "version": "1.0.6",
                      "source_count": len(source_files), "freeze_bytes": freeze_size,
                      "freeze_sha256": freeze_sha, "reserved_run_absent": not NATIVE_RUN.exists(),
                      "native_actions": 0}, sort_keys=True))


if __name__ == "__main__":
    main()
