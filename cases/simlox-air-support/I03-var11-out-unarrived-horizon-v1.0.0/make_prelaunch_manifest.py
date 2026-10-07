"""Deterministic exact source inventory; default invocation never writes."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

from verify_sources import HERE, REPO, CONTRACT_SHA, RUN_ID, verify

SCHEMA = "i03-var11-out-unarrived-prelaunch-manifest/v1"
# Filled only after exact independent file freeze.
INDEPENDENT_SHA: str | None = "08e64f0095a9cedfea45a4253418c844bf64c66aa15a4790b665ee4cde740170"
INDEPENDENT_SELFCHECK_SHA: str | None = "c2bac3ddf408c2a9df47ac9162234374ed1147ddc65cc51ee9677e80bb1617d0"
OWNED = (
    ".gitattributes", ".gitignore", "contract.json", "MODEL-LINEAGE.md",
    "README.md", "REPRODUCTION.md", "build.py", "native-input.json", "exact-diff.json",
    "check_roundtrip.py", "event_ledger.py", "report_oracle.py", "validate_native_cli.py",
    "self_check.py", "verify_sources.py", "test_sealed_catalog.py",
    "captured_process.ps1", "binary_capture_child.py", "test_captured_process.ps1",
    "checker_receipt.ps1", "test_checker_receipt.ps1", "preflight_receipt.ps1",
    "test_preflight_receipt.ps1", "run_native_ssh.ps1", "ssh_transport.py",
    "make_prelaunch_manifest.py", "root-selection-custody.json",
    "copy_root_evidence.py", "root-evidence-custody.json",
    "make_pure_evidence.py", "make_pure_evidence_v2.py",
    "make_pure_evidence_v3.py", "make_pure_evidence_v4.py",
)
DEVELOPMENT_HISTORY = (
    "runner-copied-v06-contract-sha-draft.ps1",
    "runner-copied-v06-contract-sha-draft.json",
    "catalog-live-path-draft-verify_sources.py.bytes",
    "catalog-live-path-draft-make_prelaunch_manifest.py.bytes",
    "raw-count-label-draft-run_native_ssh.ps1.bytes",
    "raw-count-label-draft-preflight_receipt.ps1.bytes",
    "raw-count-label-draft-test_preflight_receipt.ps1.bytes",
    "preflight-autoload-failed-draft.ps1.bytes",
    "preflight-receipt-getfilehash-v3.ps1.bytes",
    "test-preflight-receipt-getfilehash-v3.ps1.bytes",
)
PURE_STEP_NAMES = (
    "source_build", "root_custody", "source_verifier", "catalog_self_check",
    "author_self_check", "independent_replay", "independent_self_check",
    "checker_receipt", "preflight_receipt",
)
PURE_EVIDENCE_FILES = {
    "pure-evidence": ("receipt.json",) + tuple(
        f"{name}.{stream}.bin" for name in PURE_STEP_NAMES for stream in ("stdout", "stderr")),
    "pure-evidence-v2": ("failure-custody.json",) + tuple(
        f"{name}.{stream}.bin" for name in PURE_STEP_NAMES[:7] for stream in ("stdout", "stderr")),
    "pure-evidence-v3": ("receipt.json",) + tuple(
        f"{name}.{stream}.bin" for name in PURE_STEP_NAMES for stream in ("stdout", "stderr")),
    "pure-evidence-v4": ("receipt.json",) + tuple(
        f"{name}.{stream}.bin" for name in PURE_STEP_NAMES for stream in ("stdout", "stderr")),
}
REVIEW_HISTORY = {
    "preserved-pure-sealed-fixture-v1.py.bytes": (12312, "00a30f56be96e0307b228be88f45d77f5d91eaa06c62f84a70c2c00e1f08b271"),
    "preserved-pure-sealed-fixture-v6.py.bytes": (13276, "b735698cd28d9dfff9f6fcac4fb3279b617a8e1104eed5b443235a5fa8032cff"),
    "independent-method-custody-addendum-2026-10-08.md": (880, "08273c751afc1e3af96e8a40565f9865660b70a8831d8740df29fadb22455a4e"),
    "independent-method-note-2026-10-08.md": (2270, "2501c6ea58dc555b1dddb2546ea7a01c723f20f638144fd26bdcf818fce49b3e"),
    "independent_replay_candidate_v1.py": (69617, "00aa8a2c0fbc77a2277a1a0406c86e845b41e07fef304b95e2cda631f0f79ae5"),
    "independent_replay_candidate_v2.py": (55356, "648a50d93f845178cfd12acd63cc593071bcbd0682b1c2380ac26ef3d52b3349"),
    "independent_replay_candidate_v3.py": (56477, "72a6c41f4823dcd8ea1b9f43b93071da00e4f04d79859ec6a08715ecf53e6d32"),
    "independent_replay_candidate_v4.py": (71775, "fb75d589eb4fb4bed5aacb67ec1386179341c13393cf1710f285d5d3db1afe2d"),
    "independent_replay_candidate_v5.py": (73587, "08e64f0095a9cedfea45a4253418c844bf64c66aa15a4790b665ee4cde740170"),
    "independent_self_check_candidate_v1.py": (7433, "40503f155ce3897f0a3a582a38800681ea5e877ed68adc2c541b31205fe8dc10"),
    "independent_self_check_candidate_v2.py": (7860, "1dc8b6bebbf40c7aee1d423ea5054f468d28239dd89ab579697ab928ad8fe5bc"),
    "independent_self_check_candidate_v3.py": (10353, "bd282c8e116b9b6dda8de2ef809ed9e8ddf4197af33973576596f976924a905a"),
}


def seal(path: Path) -> dict:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def candidate(*, provisional: bool = False, mode: str = "live") -> dict:
    assert mode in ("live", "sealed")
    assert verify(mode)["passed"]
    contract = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
    lineage = contract["source_lineage"]
    custody = json.loads((HERE / "root-selection-custody.json").read_text(encoding="utf-8"))
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
    for name in DEVELOPMENT_HISTORY:
        add("owned:preserved-development/" + name, HERE / "preserved-development" / name)
    for directory, names in PURE_EVIDENCE_FILES.items():
        for name in names:
            add(f"owned:{directory}/{name}", HERE / directory / name)
    for name, (size, sha256) in REVIEW_HISTORY.items():
        add("owned:review/" + name, HERE / "review" / name,
            {"bytes": size, "sha256": sha256})
    for item in custody["records"]:
        add("owned:" + item["owned_copy"], HERE / item["owned_copy"], item)
    additional = json.loads((HERE / "root-evidence-custody.json").read_text(encoding="utf-8"))
    assert len(additional["records"]) == 38
    for item in additional["records"]:
        add("owned:" + item["owned_copy"], HERE / item["owned_copy"], item)
    add("owned:" + lineage["catalog_at_selection"]["owned_exact_archive"],
        HERE / lineage["catalog_at_selection"]["owned_exact_archive"],
        lineage["catalog_at_selection"]["local_disk"])
    if not provisional:
        assert INDEPENDENT_SHA is not None and INDEPENDENT_SELFCHECK_SHA is not None
        add("independent_replay", HERE / "review" / "independent_replay.py",
            {"bytes": (HERE / "review" / "independent_replay.py").stat().st_size,
             "sha256": INDEPENDENT_SHA})
        add("independent_self_check", HERE / "review" / "independent_self_check.py",
            {"bytes": (HERE / "review" / "independent_self_check.py").stat().st_size,
             "sha256": INDEPENDENT_SELFCHECK_SHA})
    for i, item in enumerate(lineage["primary_parent_source_and_secondary_context_source_disk_vs_git_at_base"]):
        add(f"accepted_source:{i}", REPO / item["path"], item["local_disk"])
    for i, item in enumerate(lineage["original_raw"]):
        add(f"original_raw:{i}", Path(item["original_path"]), item)
    for item in lineage["installed"]:
        add("installed:" + item["role"], Path(item["path"]), item)
    for i, item in enumerate(lineage["required_docs"]):
        add(f"required_doc:{i}", REPO / item["path"], item)
    return {"schema": SCHEMA, "run_id": RUN_ID, "contract_sha256": CONTRACT_SHA,
            "source_count": len(entries), "source_files": entries,
            "live_catalog_prelaunch_pin": {
                "path": str((REPO / lineage["catalog_at_selection"]["path"]).resolve(strict=True)),
                **lineage["catalog_at_selection"]["local_disk"]},
            "accepted_raw_records": 118, "accepted_nonclosure_raw_records": 106,
            "accepted_closure_records": 6, "accepted_invocation_records": 6,
            "excluded_failed_witness_raw_records": 26,
            "native_runs_authorized_by_manifest": 0,
            "independent_replay_state": "provisional" if provisional else "exact method pinned; fresh approval required"}


def main() -> None:
    args = sys.argv[1:]
    assert args in ([], ["--write"], ["--provisional"], ["--sealed"], ["--dry"])
    provisional = args == ["--provisional"]
    mode = "sealed" if args == ["--sealed"] else "live"
    doc = candidate(provisional=provisional, mode=mode)
    raw = (json.dumps(doc, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    path = HERE / "prelaunch-manifest.json"
    if args == ["--write"]:
        assert not path.exists(), "frozen manifest exists; preserve and version any correction"
        path.write_bytes(raw)
    elif not provisional and args != ["--dry"]:
        assert path.is_file() and path.read_bytes() == raw, "manifest absent or source drift"
    print(json.dumps({"schema": "i03-var11-out-unarrived-manifest-check/v1",
                      "passed": True, "provisional": provisional, "mode": mode,
                      "source_count": len(doc["source_files"]),
                      "manifest_sha256": hashlib.sha256(raw).hexdigest()}, separators=(",", ":")))


if __name__ == "__main__":
    main()
