"""Deterministic source inventory; final write requires final independent method pin."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

from verify_sources import HERE, REPO, verify

RUN_ID = "i03-var02-idle-out-v102-ssh-20261007-01"
CONTRACT_SHA = "1f058ae8706d4de81c28099b6580619eb4cb879e20314619f387839d9150ee29"
INDEPENDENT_SHA = "5ad26b738d0b3fc36daa494b6dfbab77c5188cb0248d0e81f365e67b7f27addc"
INDEPENDENT_SELFCHECK_SHA = "4dc362332cfe150f1e61f23ad08552231cc98d9e1805cd625f80df773b2b35ce"
OWNED = [
    ".gitattributes", ".gitignore", "contract.json", "README.md", "REPRODUCTION.md", "development-note.md",
    "build.py", "native-input.json", "exact-diff.json", "check_roundtrip.py",
    "event_ledger.py", "report_oracle.py", "validate_native_cli.py", "self_check.py",
    "verify_sources.py", "captured_process.ps1", "preflight_receipt.ps1",
    "checker_receipt.ps1", "test_preflight_receipt.ps1", "test_checker_receipt.ps1",
    "run_native_ssh.ps1", "make_prelaunch_manifest.py",
    "review/independent-contract-go-2026-10-07.md",
    "review/independent-contract-audit-v102.py",
]


def seal(path: Path) -> dict:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def candidate(provisional: bool = False) -> dict:
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
            assert pin == {k: expected[k] for k in ("bytes", "sha256")}, (key, path)
        entries.append({"key": key, "path": str(path), **pin})
    for name in OWNED:
        key = {"contract.json": "child_contract", "native-input.json": "child_input",
               "validate_native_cli.py": "behavior_validator", "run_native_ssh.ps1": "runner_script"}.get(name, "owned:"+name)
        add(key, HERE/name)
    for folder in ("preserved-v100", "preserved-v101", "preserved-root-context", "preserved-prefreeze"):
        for path in sorted((HERE/folder).rglob("*")):
            if path.is_file():
                add("owned:"+path.relative_to(HERE).as_posix(), path)
    if not provisional:
        add("independent_replay", HERE/"review/independent_replay.py",
            {"bytes": (HERE/"review/independent_replay.py").stat().st_size, "sha256": INDEPENDENT_SHA})
        add("independent_self_check", HERE/"review/independent_self_check.py",
            {"bytes": (HERE/"review/independent_self_check.py").stat().st_size, "sha256": INDEPENDENT_SELFCHECK_SHA})
    lineage = contract["source_lineage"]
    for i, item in enumerate(lineage["accepted_source_local_vs_published_git_at_base"]):
        add(f"accepted_source_local:{i}", REPO/item["path"], item["local_disk"])
    for i, item in enumerate(lineage["accepted_original_run_records"]):
        add(f"accepted_run:{i}", Path(item["path"]), item)
    for name in ("exe", "manual", "dictionary"):
        item = lineage["installed"][name]
        add("installed:"+name, Path(item["path"]), item)
    add("catalog_live_prelaunch", REPO/lineage["catalog_at_selection"]["path"],
        lineage["catalog_at_selection"]["local_disk"])
    return {"schema": "i03-var02-v102-prelaunch-manifest/v1", "run_id": RUN_ID,
            "contract_sha256": CONTRACT_SHA, "source_count": len(entries), "source_files": entries,
            "native_runs_authorized_by_manifest": 0,
            "independent_replay_state": "provisional method absent" if provisional else "final method pinned; fresh approval still required"}


def main() -> None:
    args = sys.argv[1:]
    assert args in ([], ["--write"], ["--provisional"])
    provisional = args == ["--provisional"]
    doc = candidate(provisional)
    data = (json.dumps(doc, ensure_ascii=False, sort_keys=True, indent=2)+"\n").encode("utf-8")
    out = HERE/("prelaunch-manifest-provisional.json" if provisional else "prelaunch-manifest.json")
    if provisional:
        assert not out.exists(), "provisional draft already exists; preserve exact bytes before new draft"
        out.write_bytes(data)
    elif args == ["--write"]:
        assert not out.exists(), "frozen manifest exists; version correction required"
        out.write_bytes(data)
    else:
        assert out.is_file() and out.read_bytes() == data, "manifest absent or source drift"
    print(json.dumps({"schema":"i03-var02-v102-manifest-check/v1","passed":True,
                      "provisional":provisional,"source_count":doc["source_count"],
                      "manifest_sha256":hashlib.sha256(data).hexdigest()},separators=(",", ":")))


if __name__ == "__main__":
    main()
