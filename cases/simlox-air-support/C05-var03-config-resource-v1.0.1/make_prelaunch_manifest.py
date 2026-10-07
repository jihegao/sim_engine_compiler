"""Freeze exact, reproducible prelaunch source bytes; never call SIMLOX."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from build import main as verify_build
from self_check import check as static_check
from verify_sources import verify as verify_accepted

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
CONTRACT_SHA="cc3aa75b3c4f6cec8fff57c0de28abf9ed552f4c0bc836e581295856ca30f283"
GO_SHA="77c69914b11ad2e778b231930ff97d969f9490fa255200a632a36c83c3e13243"
INPUT_SHA={"crew":"9135777819060018492d90538a1424c6fab9983e0b367f020f496dd2d37f1c67",
           "radio":"1a49e05d6100a93d2bdbbed8c046074179ead2902219f9d1495dfc6acf946f97"}


def seal(path: Path) -> dict:
    data=path.read_bytes()
    return {"path":str(path.resolve()),"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest()}


def build_manifest() -> dict:
    assert verify_accepted()["accepted_raw_seals"]==48
    assert static_check()["passed"] is True
    verify_build()
    contract=json.loads((HERE/"contract.json").read_text(encoding="utf-8-sig"))
    base=HERE.parent/"C05-var03-config-resource-v1.0.0"
    paths={
        "child_contract":HERE/"contract.json",
        "contract_review":HERE/"review/independent-contract-go-2026-10-07.md",
        "diagnostic_contract":base/"contract.json",
        "diagnostic_initial_go":base/"review/independent-contract-go-2026-10-07.md",
        "diagnostic_no_go":base/"review/independent-contract-no-go-addendum-2026-10-07.md",
        "diagnostic_correction":base/"review/independent-contract-factual-correction-2026-10-07.md",
        "diagnostic_inventory":base/"review/excluded-draft-source-inventory.json",
        "builder":HERE/"build.py",
        "crew_input":HERE/"crew-input.json",
        "radio_input":HERE/"radio-input.json",
        "exact_diff":HERE/"exact-diff.json",
        "roundtrip_checker":HERE/"check_roundtrip.py",
        "behavior_validator":HERE/"validate_native_cli.py",
        "report_oracle":HERE/"report_oracle.py",
        "static_self_check":HERE/"self_check.py",
        "accepted_source_verifier":HERE/"verify_sources.py",
        "runner_script":HERE/"run_native_ssh.ps1",
        "manifest_builder":HERE/"make_prelaunch_manifest.py",
        "prelaunch_readme":HERE/"README.md",
        "source_attributes":HERE/".gitattributes",
        "source_ignore":HERE/".gitignore",
        "priority_draft_inventory":HERE/"review/excluded-priority-draft/inventory.json",
        "physical_ledger_draft_inventory":HERE/"review/excluded-physical-ledger-draft/inventory.json",
        "physical_ledger_draft_validator":HERE/"review/excluded-physical-ledger-draft/validate_native_cli.py",
        "physical_ledger_draft_manifest":HERE/"review/excluded-physical-ledger-draft/prelaunch-manifest.json",
        "installed_exe":Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
        "installed_manual":Path(contract["installed_sources"]["manual_pdf"]["path"]),
        "installed_dictionary":Path(contract["installed_sources"]["dictionary"]["path"]),
        "python":Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
    }
    for filename in ("build.py","crew-input.json","radio-input.json","exact-diff.json",
                     "check_roundtrip.py","validate_native_cli.py"):
        paths["priority_draft_"+filename.replace(".","_").replace("-","_")]=HERE/"review/excluded-priority-draft"/filename
    for package_key,package in contract["accepted_source_pins"].items():
        for filename in package["files"]:
            paths["accepted_"+package_key+"_"+filename.replace("/","_").replace(".","_")]=HERE.parent/package["package"]/filename
    for run_key,run in contract["accepted_native_runs"].items():
        for filename in ("closure.json","invocation.json","report-raw.json"):
            paths["accepted_run_"+run_key+"_"+filename.replace("-","_").replace(".","_")]=Path(run["path"])/filename
    entries=[dict(key=key,**seal(path)) for key,path in paths.items()]
    by_key={e["key"]:e for e in entries}
    assert len(by_key)==len(entries)
    assert by_key["child_contract"]["sha256"]==CONTRACT_SHA
    assert by_key["contract_review"]["sha256"]==GO_SHA
    assert all(by_key[arm+"_input"]["sha256"]==value for arm,value in INPUT_SHA.items())
    for key,tag in (("diagnostic_contract","frozen_contract"),("diagnostic_initial_go","initial_go_memo"),
                    ("diagnostic_no_go","no_go_addendum"),("diagnostic_inventory","draft_inventory")):
        assert by_key[key]["sha256"]==contract["excluded_diagnostic"][tag]["sha256"]
    assert by_key["installed_manual"]["sha256"]==contract["installed_sources"]["manual_pdf"]["sha256"]
    assert by_key["installed_dictionary"]["sha256"]==contract["installed_sources"]["dictionary"]["sha256"]
    assert by_key["physical_ledger_draft_inventory"]["sha256"]=="77d98da713b6fd335d185fda155cd50a4136b0346f4240c26be5c96d9aaaaf7a"
    assert by_key["physical_ledger_draft_validator"]["sha256"]=="fa9b0dd2f8d2fc12b88275abbb523c95b43eaddf6b831fb693956a4b617ea2da"
    assert by_key["physical_ledger_draft_manifest"]["sha256"]=="fce232eff4e21f6f1dbb065e4f36bc166f1871f94dc97fe2cd7c3bbce671c4bb"
    return {"schema":"c05-var03-v101-prelaunch-manifest/v1","contract_sha256":CONTRACT_SHA,
            "run_ids":[contract["planned_run_ids"][a] for a in ("crew","radio")],
            "accepted_raw_seals":48,"source_files":entries,
            "approval_path":str(HERE/"review/independent-prelaunch-go.json"),
            "purpose":"Exact source inventory before one reviewed SSH0 two-arm native invocation; no native call in this builder"}


def main() -> None:
    manifest=build_manifest()
    data=(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n").encode()
    path=HERE/"prelaunch-manifest.json"
    if path.exists():
        assert path.read_bytes()==data,"frozen prelaunch manifest drift"
    else:
        path.write_bytes(data)
    print(json.dumps({"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest(),
                      "source_count":len(manifest["source_files"])}))


if __name__=="__main__":
    main()
