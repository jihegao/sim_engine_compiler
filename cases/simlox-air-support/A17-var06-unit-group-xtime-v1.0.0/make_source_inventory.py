"""Closed, ordered A17.var06 prelaunch source inventory; no native execution."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
INVENTORY = HERE / "source-inventory.json"
OWNED = (
    ".gitattributes", "build.py", "captured_process.ps1", "check_roundtrip.py",
    "checker_receipt.ps1", "child-roundtrip-oracle.json", "event_ledger.py",
    "execution-contract.json", "make_prelaunch_manifest.py",
    "make_source_inventory.py", "model_common.py", "native-input.json",
    "preflight_receipt.ps1", "prospective-log-oracle.bytes",
    "report_oracle.py", "run_native_ssh.ps1", "self_check.py",
    "source_gate.py", "ssh_transport.py", "test_converter_gate.ps1",
    "validate_native_cli.py",
    "preserved-context/root-selection-receipt.json",
    "preserved-design/contract.json", "preserved-design/oracle-map.json",
    "preserved-design/README.md", "preserved-design/independent-contract-go.md",
    "preserved-design/author-child-build-v100.py.bytes",
    "preserved-design/independent-audit-v100-unexecuted.py.bytes",
    "preserved-design/independent-audit-v101.py.bytes",
    "preserved-design/independent-audit-receipt.json",
    "preserved-design/independent-audit-stdout.bin",
    "preserved-design/independent-audit-stderr.bin",
    "preserved-development/self-check-v1-log-index-assumption.py.bytes",
    "preserved-development/self-check-v1-log-index-assumption.md",
    "preserved-development/self-check-v2-bool-equality-assumption.py.bytes",
    "preserved-development/self-check-v2-bool-equality-assumption.md",
    "preserved-development/template-a17-var01-captured_process.ps1.bytes",
    "preserved-development/template-a17-var01-checker_receipt.ps1.bytes",
    "preserved-development/template-a17-var01-make_prelaunch_manifest.py.bytes",
    "preserved-development/template-a17-var01-make_source_inventory.py.bytes",
    "preserved-development/template-a17-var01-preflight_receipt.ps1.bytes",
    "preserved-development/template-a17-var01-run_native_ssh.ps1.bytes",
    "preserved-development/template-a17-var01-ssh_transport.py.bytes",
    "preserved-development/template-a17-var01-test_converter_gate.ps1.bytes",
    "review/independent_reader.py", "review/independent_self_check.py",
    "review/independent-static-go-2026-10-09.md",
    "source-maps/accepted-source-pairs.json", "source-maps/prospective-source-pins.json",
)
FUTURE_FILES = frozenset({
    "README-publication.md", "REPRODUCTION-postrun.md", "results-summary.json",
    "publication-entry.json", "cli-scope-signoff-2026-10-09.md",
    "make_evidence_index.py", "evidence-index.json",
})
FUTURE_REVIEW_PREFIXES = (
    "preflight-ssh0-", "independent-prelaunch-", "independent-postrun-",
    "independent-content-",
)
GENERATED_TOP = frozenset({"runs", "test-output", "transport-evidence", "__pycache__"})
INERT_TOP = {"preserved-postrun": "postrun", "preserved-raw": "raw", "preserved-preflight": "preflight"}


def excluded(rel: str) -> bool:
    parts = rel.split("/")
    if parts[0] in GENERATED_TOP:
        return True
    if len(parts) == 2 and parts[0] in INERT_TOP:
        stem = INERT_TOP[parts[0]]
        return parts[1] == "custody.json" or re.fullmatch(rf"{stem}-[0-9]{{3}}\.bytes", parts[1]) is not None
    if rel in FUTURE_FILES or rel == INVENTORY.name or rel == "prelaunch-manifest.json":
        return True
    if len(parts) == 2 and parts[0] == "review":
        return any(parts[1].startswith(prefix) for prefix in FUTURE_REVIEW_PREFIXES)
    return False


def document() -> dict:
    assert len(OWNED) == len(set(OWNED))
    observed = set()
    for root, dirs, files in os.walk(HERE, topdown=True, followlinks=False):
        root_path = Path(root)
        if root_path == HERE:
            dirs[:] = [name for name in dirs if name not in GENERATED_TOP]
        for name in dirs:
            candidate = root_path / name
            assert not candidate.is_symlink() and not (candidate.stat().st_file_attributes & 0x400), str(candidate)
        for name in files:
            path = root_path / name
            rel = path.relative_to(HERE).as_posix()
            if not excluded(rel):
                observed.add(rel)
    assert observed == set(OWNED), {"missing": sorted(set(OWNED) - observed), "unknown": sorted(observed - set(OWNED))}
    rows = []
    for rel in OWNED:
        path = HERE / rel
        assert path.is_file() and not path.is_symlink()
        assert path.stat().st_file_attributes & 0x1, f"owned source is writable: {rel}"
        data = path.read_bytes()
        rows.append({"path": rel, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()})
    return {"schema": "a17-var06-source-inventory/v100", "source_count": len(rows), "source_files": rows}


def encode(value: dict) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--candidate", type=Path)
    group.add_argument("--write", action="store_true")
    args = parser.parse_args()
    body = encode(document())
    if args.candidate is not None:
        assert args.candidate.is_absolute() and not args.candidate.is_relative_to(HERE)
        with args.candidate.open("xb") as stream:
            stream.write(body)
    elif args.write:
        with INVENTORY.open("xb") as stream:
            stream.write(body)
    else:
        assert INVENTORY.read_bytes() == body, "canonical source inventory differs"
    print(json.dumps({"schema": "a17-var06-source-inventory-check/v100", "source_count": len(OWNED),
                      "sha256": hashlib.sha256(body).hexdigest(), "passed": True}, sort_keys=True))


if __name__ == "__main__":
    main()
