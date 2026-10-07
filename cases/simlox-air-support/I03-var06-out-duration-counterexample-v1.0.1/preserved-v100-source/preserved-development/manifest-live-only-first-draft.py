"""Fixed prelaunch source inventory; default invocation is read-only."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

from verify_sources import HERE, REPO, verify, CONTRACT_SHA, RUN_ID

SCHEMA = "i03-var06-out-dt4-prelaunch-manifest/v1"
# Set only after the independent reviewer freezes the exact file. Until then,
# --provisional produces schema feedback without writing any manifest.
INDEPENDENT_SHA: str | None = None
OWNED = (
    ".gitattributes", ".gitignore", "contract.json", "development-note.md",
    "README.md", "REPRODUCTION.md", "build.py", "native-input.json",
    "exact-diff.json", "check_roundtrip.py", "event_ledger.py",
    "report_oracle.py", "validate_native_cli.py", "self_check.py",
    "verify_sources.py", "test_sealed_catalog.py", "captured_process.ps1",
    "binary_capture_child.py", "test_captured_process.ps1",
    "checker_receipt.ps1", "test_checker_receipt.ps1",
    "preflight_receipt.ps1", "test_preflight_receipt.ps1",
    "run_native_ssh.ps1", "ssh_transport.py", "make_prelaunch_manifest.py",
    "root-context-custody.json",
)
REVIEW_HISTORY = (
    "independent-contract-go-2026-10-08.md",
    "independent-contract-audit-2026-10-08.py",
    "excluded-contract-audit-draft-v1.py",
    "excluded-contract-audit-draft-v1.stdout.txt",
    "excluded-contract-audit-draft-v1.stderr.txt",
    "excluded-self-check-draft-v1.py",
    "excluded-self-check-draft-v1.stdout.txt",
    "excluded-self-check-draft-v1.stderr.txt",
    "excluded-self-check-draft-v2.py",
    "excluded-self-check-draft-v2.stdout.txt",
    "excluded-self-check-draft-v2.stderr.txt",
)
DEVELOPMENT_HISTORY = (
    "binary-first-draft-captured_process.ps1",
    "binary-first-draft-test_captured_process.ps1",
    "binary-first-draft-failure.md",
    "binary-second-draft-captured_process.ps1",
    "binary-second-draft-test_captured_process.ps1",
    "binary-second-draft-risk.md",
    "binary-third-draft-captured_process.ps1",
    "binary-third-draft-test_captured_process.ps1",
    "binary-third-draft-binary_capture_child.py",
    "binary-third-draft-async-risk.md",
    "verify_sources-git-tree-first-draft.py",
    "verify_sources-git-tree-first-draft-error.md",
    "decoder-first-draft-check_roundtrip.py",
)


def seal(path: Path) -> dict:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def candidate(provisional: bool) -> dict:
    assert verify("live")["passed"]
    contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
    assert contract["run_id"] == RUN_ID
    entries: list[dict] = []
    keys: set[str] = set()

    def add(key: str, path: Path, expected: dict | None = None) -> None:
        path = path.resolve(strict=True)
        assert path.is_file() and key not in keys, (key, path)
        keys.add(key)
        pin = seal(path)
        if expected is not None:
            assert pin == {k: expected[k] for k in ("bytes", "sha256")}, key
        entries.append({"key": key, "path": str(path), **pin})

    role = {"contract.json": "child_contract", "native-input.json": "child_input",
            "validate_native_cli.py": "behavior_validator", "run_native_ssh.ps1": "runner_script"}
    for name in OWNED:
        add(role.get(name, "owned:" + name), HERE / name)
    for name in REVIEW_HISTORY:
        add("owned:review/" + name, HERE / "review" / name)
    for name in DEVELOPMENT_HISTORY:
        add("owned:preserved-development/" + name, HERE / "preserved-development" / name)
    custody = json.loads((HERE / "root-context-custody.json").read_text(encoding="utf-8"))
    assert len(custody["records"]) == 12
    for item in custody["records"]:
        add("owned:" + item["owned_copy"], HERE / item["owned_copy"], item)
    if not provisional:
        assert INDEPENDENT_SHA is not None
        add("independent_replay", HERE / "review" / "independent_replay.py",
            {"bytes": (HERE / "review" / "independent_replay.py").stat().st_size,
             "sha256": INDEPENDENT_SHA})
    lineage = contract["source_lineage"]
    for section in ("parent_source_disk_and_git_at_base",
                    "accepted_dependency_source_disk_and_git_at_base",
                    "accepted_secondary_context_source_disk_and_git_at_base"):
        for i, item in enumerate(lineage[section]):
            add(f"accepted_source:{section}:{i}", REPO / item["path"], item["local_disk"])
    for section in ("accepted_parent_and_context_raw", "accepted_secondary_context_run_files"):
        for i, item in enumerate(lineage[section]):
            add(f"accepted_run:{section}:{i}", Path(item["original_path"]), item)
    for item in lineage["installed"]:
        add("installed:" + item["role"], Path(item["path"]), item)
    for i, item in enumerate(lineage["required_docs"]):
        add(f"required_doc:{i}", REPO / item["path"], item)
    add("catalog_live_prelaunch", REPO / lineage["catalog_at_selection"]["path"],
        lineage["catalog_at_selection"]["local_disk"])
    return {"schema": SCHEMA, "run_id": RUN_ID, "contract_sha256": CONTRACT_SHA,
            "source_count": len(entries), "source_files": entries,
            "native_runs_authorized_by_manifest": 0,
            "independent_replay_state": "provisional" if provisional else "exact method pinned; fresh approval required"}


def main() -> None:
    args = sys.argv[1:]
    assert args in ([], ["--write"], ["--provisional"])
    provisional = args == ["--provisional"]
    doc = candidate(provisional)
    raw = (json.dumps(doc, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    path = HERE / "prelaunch-manifest.json"
    if args == ["--write"]:
        assert not path.exists(), "prelaunch manifest already exists; preserve and version any correction"
        path.write_bytes(raw)
    elif not provisional:
        assert path.is_file() and path.read_bytes() == raw, "manifest missing or source drift"
    print(json.dumps({"schema": "i03-var06-out-dt4-manifest-check/v1",
                      "passed": True, "provisional": provisional,
                      "source_count": doc["source_count"],
                      "manifest_sha256": hashlib.sha256(raw).hexdigest()}, separators=(",", ":")))


if __name__ == "__main__":
    main()
