"""Seal exact prelaunch source bytes; never invokes SIMLOX."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
REPO = HERE.parents[2]
CONTRACT_SHA = "5458f7b0615ecd8e25d1cba9fd25b14151297112c4446f29eb8bac3371ad31a3"
REVIEW_SHA = "a57a67110e5b0f84caf20009f32d6df61582341c8f74454c46a20f499373a010"
INPUT_SHA = {"joint": "b75ee0be384fd873f3a72e14d6f4a236caa43f86eb77cabe06892acf8be01d4c",
             "crewonly": "c28befdede5855f145132784e49a2d2eb965f529f3a150f85f8a7099f4a310f5"}


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def seal(path: Path) -> dict:
    raw = path.read_bytes()
    return {"path": str(path.resolve()), "bytes": len(raw), "sha256": sha(raw)}


def verify_published(package: str, listing: dict) -> list[dict]:
    result = []
    for relative, pin in listing.items():
        path = ROOT / package / relative
        local = path.read_bytes()
        git_rel = path.relative_to(REPO).as_posix()
        published = subprocess.check_output(["git", "show", "HEAD:" + git_rel], cwd=REPO)
        assert len(local) == pin["local_bytes"] and sha(local) == pin["local_sha256"], relative
        assert len(published) == pin["published_git_bytes"] and sha(published) == pin["published_git_sha256"], relative
        result.append({"key": f"published_{package}_{relative}", **seal(path)})
    return result


def main() -> None:
    contract = json.loads((HERE / "contract.json").read_bytes())
    assert seal(HERE / "contract.json")["sha256"] == CONTRACT_SHA
    paths = {
        "child_contract": HERE / "contract.json",
        "contract_review": HERE / "review" / "independent-contract-go-2026-10-07.md",
        "builder": HERE / "build.py",
        "joint_input": HERE / "joint-input.json",
        "crewonly_input": HERE / "crewonly-input.json",
        "exact_diff": HERE / "exact-diff.json",
        "roundtrip_checker": HERE / "check_roundtrip.py",
        "behavior_validator": HERE / "validate_native_cli.py",
        "static_negative_checks": HERE / "self_check.py",
        "runner_script": HERE / "run_native_ssh.ps1",
        "manifest_builder": HERE / "make_prelaunch_manifest.py",
        "excluded_draft_manifest": HERE / "review" / "excluded-draft-prelaunch-manifest.json",
        "excluded_draft_runner": HERE / "review" / "excluded-draft-runner.ps1",
        "excluded_draft_validator": HERE / "review" / "excluded-draft-validator.py",
        "excluded_draft_self_check": HERE / "review" / "excluded-draft-self-check.py",
        "excluded_draft_manifest_builder": HERE / "review" / "excluded-draft-manifest-builder.py",
        "excluded_draft_note": HERE / "review" / "excluded-draft-prelaunch-note.md",
        "source_attributes": HERE / ".gitattributes",
        "source_ignore": HERE / ".gitignore",
        "accepted_parent_input": ROOT / "C02-joint-resources-v1.0.2" / "inputs" / "single-equipment-zero.json",
        "accepted_positive_input": ROOT / "C02-joint-resources-v1.0.2" / "inputs" / "single-both.json",
        "accepted_parent_closure": Path(contract["accepted_evidence"]["C02"]["single_equipment_zero"]["path"]) / "closure.json",
        "accepted_parent_invocation": Path(contract["accepted_evidence"]["C02"]["single_equipment_zero"]["path"]) / "invocation.json",
        "accepted_parent_report": Path(contract["accepted_evidence"]["C02"]["single_equipment_zero"]["path"]) / "report-raw.json",
        "accepted_positive_closure": Path(contract["accepted_evidence"]["C02"]["single_both_context"]["path"]) / "closure.json",
        "accepted_positive_invocation": Path(contract["accepted_evidence"]["C02"]["single_both_context"]["path"]) / "invocation.json",
        "accepted_positive_report": Path(contract["accepted_evidence"]["C02"]["single_both_context"]["path"]) / "report-raw.json",
        "accepted_c01_input": ROOT / "C01-personnel-capacity-v1.0.2" / "inputs" / "capacity-2.json",
        "accepted_c01_closure": Path(contract["accepted_evidence"]["C01"]["capacity_two_context"]["path"]) / "closure.json",
        "accepted_c01_invocation": Path(contract["accepted_evidence"]["C01"]["capacity_two_context"]["path"]) / "invocation.json",
        "installed_exe": Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
        "installed_manual": Path(contract["manual"]["installed_pdf"]),
        "installed_dictionary": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
        "python": Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
    }
    entries = [dict(key=key, **seal(path)) for key, path in paths.items()]
    for case in ("C02", "C01"):
        package = contract["accepted_evidence"][case]["package"]
        entries += verify_published(package, contract["accepted_evidence"][case]["published_source"])
    by_key = {entry["key"]: entry for entry in entries}
    assert by_key["contract_review"]["sha256"] == REVIEW_SHA
    assert by_key["joint_input"]["sha256"] == INPUT_SHA["joint"]
    assert by_key["crewonly_input"]["sha256"] == INPUT_SHA["crewonly"]
    assert by_key["accepted_parent_input"]["sha256"] == contract["source_design"]["parent_input_pin"]["sha256"]
    assert by_key["accepted_positive_input"]["sha256"] == contract["source_design"]["positive_context_input_pin"]["sha256"]
    for label, case, arm in (("parent", "C02", "single_equipment_zero"),
                              ("positive", "C02", "single_both_context"),
                              ("c01", "C01", "capacity_two_context")):
        for kind in ("closure", "invocation"):
            assert by_key[f"accepted_{label}_{kind}"]["sha256"] == contract["accepted_evidence"][case][arm][kind]["sha256"]
    assert by_key["installed_manual"]["sha256"] == contract["manual"]["pin"]["sha256"]
    assert by_key["excluded_draft_manifest"]["sha256"] == "014c6be1acf803ff6cc16dbabd87408c344471dd46e9981754ebeeb9ce07ea5f"
    assert by_key["excluded_draft_runner"]["sha256"] == "ede2a3004f96508d60486dfbec640ac7b37e7d823cbfd1450ad0acb483b7c9be"
    assert by_key["excluded_draft_validator"]["sha256"] == "179c8d3cd2d872c3bdf082343fab1469dac35d9684c114672996e3b6a6f60aba"
    assert by_key["excluded_draft_self_check"]["sha256"] == "358b01913c895067f10c034e6d1d97c68cca68416f9fd3e8d12ceca66f83af4c"
    assert by_key["excluded_draft_manifest_builder"]["sha256"] == "adeb13b6ad4a65a324ae748c7ce9d0d6468c239940904020862cc171337b8b3d"
    document = {
        "schema": "c02-var04-v100-prelaunch-manifest/v1", "contract_sha256": CONTRACT_SHA,
        "run_ids": contract["ownership"]["planned_run_ids"],
        "accepted_parent_closure_sha256": by_key["accepted_parent_closure"]["sha256"],
        "accepted_positive_closure_sha256": by_key["accepted_positive_closure"]["sha256"],
        "accepted_c01_closure_sha256": by_key["accepted_c01_closure"]["sha256"],
        "source_files": entries,
        "approval_path": str(HERE / "review" / "independent-prelaunch-go.json"),
        "purpose": "Exact source inventory before one guarded serial two-arm SSH0 native invocation; this builder makes no native call",
    }
    data = (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode()
    path = HERE / "prelaunch-manifest.json"
    if path.exists():
        assert path.read_bytes() == data, "frozen manifest differs"
    else:
        path.write_bytes(data)
    print(len(data), sha(data), len(entries))


if __name__ == "__main__":
    main()
