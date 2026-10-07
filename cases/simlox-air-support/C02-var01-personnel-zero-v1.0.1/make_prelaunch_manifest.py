"""Construct one exact prelaunch source inventory; default only verifies frozen bytes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

from verify_sources import verify, REPO, CASES, HERE

OUT = HERE / "prelaunch-manifest.json"
RUN_ID = "c02-var01-v101-personnel0-ssh-20261007-01"
OWNED = [
    ".gitattributes", ".gitignore", "contract.json", "README.md", "development-note.md",
    "build.py", "native-input.json", "exact-diff.json", "check_roundtrip.py",
    "report_oracle.py", "validate_native_cli.py", "self_check.py", "verify_sources.py",
    "captured_process.ps1", "preflight_receipt.ps1", "test_preflight_receipt.ps1",
    "checker_receipt.ps1", "test_checker_receipt.ps1",
    "run_native_ssh.ps1", "make_prelaunch_manifest.py", "REPRODUCTION.md",
    "review/independent-contract-go-2026-10-07.md", "review/independent_contract_audit.py",
    "review/independent_replay.py",
]


def seal(path: Path) -> dict:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def candidate() -> dict:
    assert verify()["passed"]
    contract = json.loads((HERE / "contract.json").read_bytes())
    assert contract["ownership"]["sole_new_run_id"] == RUN_ID
    entries = []
    keys = set()

    def add(key: str, path: Path, pin: dict | None = None) -> None:
        path = path.resolve(strict=True)
        assert key not in keys and path.is_file(), (key, path)
        keys.add(key)
        identity = seal(path)
        if pin is not None:
            assert identity == {"bytes": pin["bytes"], "sha256": pin["sha256"]}, key
        entries.append({"key": key, "path": str(path), **identity})

    for name in OWNED:
        key = {"contract.json": "child_contract", "native-input.json": "child_input",
               "validate_native_cli.py": "behavior_validator", "run_native_ssh.ps1": "runner_script"}.get(name, "owned:" + name)
        add(key, HERE / name)
    for folder in ("preserved-context", "preserved-prefreeze"):
        for path in sorted((HERE / folder).rglob("*")):
            if path.is_file():
                add("owned:" + path.relative_to(HERE).as_posix(), path)
    evidence = contract["accepted_evidence"]
    classification = evidence["classification"]
    for i, pin in enumerate(classification["source_files"]):
        add(f"classification_source:{i}", CASES / classification["package"] / pin["path"], pin)
    parent = evidence["C02_parent"]
    for i, pin in enumerate(parent["source_files_dual_local_and_git"]):
        add(f"parent_source_local:{i}", CASES / parent["package"] / pin["path"], pin["local_disk"])
    for i, accepted in enumerate(parent["accepted_runs"]):
        root = Path(accepted["local_run_dir"])
        add(f"parent_run:{i}:closure", root / "closure.json", accepted["closure"])
        add(f"parent_run:{i}:invocation", root / "invocation.json", accepted["invocation"])
        for name, pin in sorted(accepted["raw"].items()):
            add(f"parent_run:{i}:raw:{name}", root / name, pin)
    c01 = evidence["C01_capacity_zero_context"]
    for i, (name, pin) in enumerate(sorted(c01["source_files_dual_local_and_git"].items())):
        add(f"c01_source_local:{i}", CASES / c01["package"] / name,
            {"bytes": pin["local_bytes"], "sha256": pin["local_sha256"]})
    root = Path(c01["local_run_dir"])
    for name in ("closure", "invocation"):
        add(f"c01_run:{name}", root / c01[name]["path"], c01[name])
    for name, pin in sorted(c01["raw"].items()):
        add(f"c01_run:raw:{name}", root / name, pin)
    for i, pin in enumerate(contract["excluded_v100"]["files"]):
        add(f"excluded_v100:{i}", CASES / pin["path"], pin)
    for name in ("exe", "manual", "dictionary"):
        add("installed:" + name, Path(contract["installed"][name]["path"]), contract["installed"][name])
    for name in ("source", "execution_plan", "publication_index_at_selection"):
        pin = contract["catalog"][name]
        add("catalog:" + name, REPO / pin["path"], pin)
    pin = contract["ownership"]["historical_v100_selection_context"]
    add("root_selection_original", REPO / pin["path"], pin)
    add("root_instructions_original", REPO / "tmp/c02-var01-root-instructions-20261007.json",
        seal(HERE / "preserved-context/c02-var01-root-instructions-20261007.json"))
    return {"schema": "c02-var01-v101-prelaunch-manifest/v1",
            "run_id": RUN_ID, "contract_sha256": seal(HERE / "contract.json")["sha256"],
            "source_count": len(entries), "source_files": entries,
            "native_runs_authorized_by_manifest": 0,
            "independent_replay_state": "method source pinned; fresh approval separately binds final SHA"}


def main() -> None:
    data = (json.dumps(candidate(), ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    if "--write" in sys.argv:
        assert not OUT.exists(), "frozen manifest exists; version correction required"
        OUT.write_bytes(data)
    else:
        assert OUT.is_file() and OUT.read_bytes() == data, "manifest absent or source drift"
    print(json.dumps({"schema": "c02-var01-v101-manifest-check/v1", "passed": True,
                      "source_count": json.loads(data)["source_count"],
                      "manifest_sha256": hashlib.sha256(data).hexdigest()}, separators=(",", ":")))


if __name__ == "__main__":
    main()
