"""Freeze exact source-byte inventory for independent SSH prelaunch review."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
CONTRACT_SHA = "48a29f63e819e85dc3f9de856199c63441f32f34104dade338ef1ca246bd2384"


def seal(path: Path) -> dict:
    data = path.read_bytes()
    return {"path": str(path.resolve()), "bytes": len(data),
            "sha256": hashlib.sha256(data).hexdigest()}


def main() -> None:
    contract = json.loads((HERE / "contract.json").read_bytes())
    assert seal(HERE / "contract.json")["sha256"] == CONTRACT_SHA
    paths = {
        "child_contract": HERE / "contract.json",
        "contract_review": HERE / "review" / "independent-contract-go-2026-10-07.md",
        "diagnostic_contract": ROOT / "C06-var03-multiple-artf-v1.0.0" / "contract.json",
        "diagnostic_review": ROOT / "C06-var03-multiple-artf-v1.0.0" / "review" / "independent-contract-no-go-2026-10-07.md",
        "builder": HERE / "build.py",
        "factor1_input": HERE / "factor1-input.json",
        "factor3_input": HERE / "factor3-input.json",
        "exact_diff": HERE / "exact-diff.json",
        "roundtrip_checker": HERE / "check_roundtrip.py",
        "behavior_validator": HERE / "validate_native_cli.py",
        "static_negative_checks": HERE / "self_check.py",
        "runner_script": HERE / "run_native_ssh.ps1",
        "manifest_builder": HERE / "make_prelaunch_manifest.py",
        "excluded_draft_manifest": HERE / "review" / "excluded-draft-prelaunch-manifest.json",
        "excluded_draft_runner": HERE / "review" / "excluded-draft-runner.ps1",
        "excluded_draft_manifest_builder": HERE / "review" / "excluded-draft-manifest-builder.py",
        "excluded_draft_note": HERE / "review" / "excluded-draft-prelaunch-note.md",
        "source_attributes": HERE / ".gitattributes",
        "source_ignore": HERE / ".gitignore",
        "accepted_parent_input": ROOT / "C06-alternative-resource-v1.0.0" / "primary-0-artf-2-input.json",
        "accepted_parent_contract": ROOT / "C06-alternative-resource-v1.0.0" / "contract.json",
        "accepted_parent_signoff": ROOT / "C06-alternative-resource-v1.0.0" / "cli-scope-signoff-2026-09-30.md",
        "accepted_parent_closure": Path(contract["accepted_C06_parent"]["run"]["path"]) / "closure.json",
        "accepted_parent_invocation": Path(contract["accepted_C06_parent"]["run"]["path"]) / "invocation.json",
        "accepted_parent_report": Path(contract["accepted_C06_parent"]["run"]["path"]) / "report-raw.json",
        "accepted_c03_input": ROOT / "C03-shared-crew-formation-v1.0.2" / "inputs" / "staffing-2.json",
        "accepted_c03_closure": Path(contract["accepted_C03_prerequisite"]["staffing_2_run"]["path"]) / "closure.json",
        "installed_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
        "installed_manual": Path(contract["manual"]["installed_pdf"]),
        "installed_dictionary": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
        "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
    }
    entries = [dict(key=key, **seal(path)) for key, path in paths.items()]
    by_key = {entry["key"]: entry for entry in entries}
    assert by_key["contract_review"]["sha256"] == "e812a38a3bdc330ac4b0ebf355a0b976303c11586df8f99cfbf210d9601830fb"
    assert by_key["diagnostic_contract"]["sha256"] == contract["excluded_diagnostic"]["frozen_contract"]["sha256"]
    assert by_key["diagnostic_review"]["sha256"] == contract["excluded_diagnostic"]["independent_no_go_memo"]["sha256"]
    assert by_key["accepted_parent_input"]["sha256"] == contract["accepted_C06_parent"]["input"]["local_disk"]["sha256"]
    assert by_key["accepted_parent_closure"]["sha256"] == contract["accepted_C06_parent"]["run"]["closure"]["sha256"]
    assert by_key["accepted_c03_input"]["sha256"] == contract["accepted_C03_prerequisite"]["staffing_2_input"]["local_disk"]["sha256"]
    assert by_key["accepted_c03_closure"]["sha256"] == contract["accepted_C03_prerequisite"]["staffing_2_run"]["closure"]["sha256"]
    assert by_key["installed_manual"]["sha256"] == contract["manual"]["seal"]["sha256"]
    assert by_key["factor1_input"]["sha256"] == "c9da3e83e4b270ab93c02c167932f86cfee2096a8aeb5947de7bad7a77cc2231"
    assert by_key["factor3_input"]["sha256"] == "074c9e098edc0e81746dfb9978c6610b1be17a967bbbbc5c4f8949bd5a0bb1d3"
    assert by_key["excluded_draft_manifest"]["sha256"] == "39c0279333c1c81e8c2bc22b638a55b952108b871129051bac5585d6ead275e7"
    assert by_key["excluded_draft_runner"]["sha256"] == "4109fa097e7cac28a7444b144357700b482e599ed4a7cc667615f8c81e43659b"
    assert by_key["excluded_draft_manifest_builder"]["sha256"] == "dfb5617524496b07fd7757ae0d86948ecc316a6cf29af00d18679a2f4f91a021"
    manifest = {
        "schema": "c06-var03-v101-prelaunch-manifest/v1",
        "contract_sha256": CONTRACT_SHA,
        "run_ids": ["c06-var03-v101-factor1-ssh-20261007-01", "c06-var03-v101-factor3-ssh-20261007-01"],
        "accepted_parent_closure_sha256": by_key["accepted_parent_closure"]["sha256"],
        "accepted_c03_closure_sha256": by_key["accepted_c03_closure"]["sha256"],
        "source_files": entries,
        "approval_path": str(HERE / "review" / "independent-prelaunch-go.json"),
        "purpose": "Exact file inventory before a single protected two-arm SSH0 native execution; no native call in this builder",
    }
    raw = (json.dumps(manifest, indent=2, ensure_ascii=False) + "\n").encode()
    path = HERE / "prelaunch-manifest.json"
    if path.exists():
        assert path.read_bytes() == raw, "frozen manifest differs"
    else:
        path.write_bytes(raw)
    print(len(raw), hashlib.sha256(raw).hexdigest(), len(entries))


if __name__ == "__main__":
    main()
