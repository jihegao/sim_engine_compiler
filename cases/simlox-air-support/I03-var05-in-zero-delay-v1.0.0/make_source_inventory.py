"""Closed owned-source inventory. Only root writes the canonical file once."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
SCHEMA = "i03-var05-in-zero-owned-source-inventory/v1"

OWNED = (
    ".gitattributes", ".gitignore", "contract.json", "execution-contract.json",
    "README.md", "REPRODUCTION.md", "build.py", "native-input.json", "exact-diff.json",
    "check_roundtrip.py", "event_ledger.py", "report_oracle.py", "validate_native_cli.py",
    "source_gate.py", "self_check.py", "copy_context.py", "context-custody.json",
    "context-custody-v2.json", "captured_process.ps1", "checker_receipt.ps1",
    "preflight_receipt.ps1", "run_native_ssh.ps1", "ssh_transport.py",
    "test_converter_gate.ps1", "test_sealed_catalog.py", "pure_proof.py", "copy_pure_proof.py", "pure-proof-custody.json",
    "make_source_inventory.py", "make_prelaunch_manifest.py",
)
PRESERVED = (
    "checker-inherited-var11-scaffold.ps1.bytes",
    "copy-pure-proof-original-required-draft.py.bytes",
    "context-custody-v1-live-equality-draft.json.bytes",
    "copy-context-live-catalog-equality-draft.py.bytes",
    "event-ledger-pre-owner-draft.py.bytes",
    "preflight-inherited-var11-scaffold.ps1.bytes",
    "roundtrip-pre-overflow-draft.py.bytes",
    "runner-inherited-var11-scaffold.ps1.bytes",
    "self-check-incomplete-draft.py.bytes",
    "self-check-v1-passing-draft.py.bytes",
    "self-check-live-catalog-draft.py.bytes",
    "source-gate-live-catalog-equality-draft.py.bytes",
    "source-gate-pre-overflow-draft.py.bytes",
    "test-converter-getfilehash-failed-draft.ps1.bytes",
)
REVIEW = (
    "independent_replay.py", "independent_self_check.py",
    "independent-method-static-go-2026-10-08.md",
    "independent_replay_candidate_v1.py", "independent_replay_candidate_v1_failure.md",
    "independent_replay_candidate_v2.py", "independent_replay_candidate_v2_failure.md",
    "independent_replay_candidate_v3.py", "independent_replay_candidate_v3_failure.md",
    "independent_replay_candidate_v4.py", "independent_replay_candidate_v5.py",
    "independent_replay_candidate_v5_failure.md", "independent_replay_candidate_v6.py",
    "independent_replay_candidate_v7.py", "independent_replay_candidate_v7_failure.md",
    "independent_replay_candidate_v8.py", "independent_replay_candidate_v8_static_no_go.md",
    "independent_self_check_candidate_v1.py", "independent_self_check_candidate_v1_failure.md",
    "independent_self_check_candidate_v2.py", "independent_self_check_candidate_v2_failure.md",
)


def pin(path: Path) -> dict:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def paths(*, provisional: bool) -> list[str]:
    names = list(OWNED)
    names.extend("preserved-development/" + name for name in PRESERVED)
    names.extend(f"preserved-context/c{index:03d}.bytes" for index in range(1, 18))
    names.extend(f"preserved-pure-proof/p{proof:01d}-{index:02d}.bytes"
                 for proof, count in ((1, 11), (2, 15)) for index in range(1, count + 1))
    if not provisional:
        names.extend("review/" + name for name in REVIEW)
    assert len(names) == len(set(names))
    return names


def candidate(*, provisional: bool = False) -> dict:
    records = []
    for relative in paths(provisional=provisional):
        path = HERE / relative
        assert path.is_file(), relative
        records.append({"relative_path": relative, "path": str(path.resolve(strict=True)), **pin(path)})
    assert len({row["path"] for row in records}) == len(records)
    return {"schema": SCHEMA, "source_count": len(records), "source_files": records,
            "provisional_independent_methods_absent": provisional,
            "excluded_future": ["source-inventory.json", "prelaunch-manifest.json", "runs/",
                                "transport-evidence/", "test-output/", "review/independent-prelaunch-",
                                "review/independent-postrun-", "review/independent-content-"]}


def body(doc: dict) -> bytes:
    return (json.dumps(doc, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def main() -> None:
    args = sys.argv[1:]
    assert args in ([], ["--dry"], ["--provisional"], ["--write"])
    provisional = args == ["--provisional"]
    data = body(candidate(provisional=provisional))
    output = HERE / "source-inventory.json"
    if args == ["--write"]:
        assert not output.exists(), "canonical owned inventory already exists"
        output.write_bytes(data)
    elif args == []:
        assert output.is_file() and output.read_bytes() == data
    print(json.dumps({"schema": SCHEMA, "source_count": json.loads(data)["source_count"],
                      "inventory_sha256": hashlib.sha256(data).hexdigest(),
                      "written": args == ["--write"], "provisional": provisional}, sort_keys=True))


if __name__ == "__main__":
    main()
