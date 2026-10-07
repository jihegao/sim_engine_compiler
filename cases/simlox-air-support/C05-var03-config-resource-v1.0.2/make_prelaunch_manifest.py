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
CONTRACT_SHA="b397b217fbf19ec9b6ae9a166a7b3124144f7ec74680675b1fc47b3b69469d0f"
GO_SHA="e83e8584bcee37fd3fe8b69646202ed25d31defc78151e24e6689421d6ae4b93"
INPUT_SHA={"crew":"6c88e8f5b078e7d02184d8612acda6b5d20ed94398943a7ca7f3472830c2f7ae",
           "radio":"235a6ce2850fb12dc5d3f4da67e709e8646fa2f4f6e2aa9cee3e106da335f57a"}


def seal(path: Path) -> dict:
    data=path.read_bytes()
    return {"path":str(path.resolve()),"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest()}


def build_manifest() -> dict:
    assert verify_accepted()["accepted_raw_seals"]==48
    assert static_check()["passed"] is True
    verify_build()
    contract=json.loads((HERE/"contract.json").read_text(encoding="utf-8-sig"))
    base=HERE.parent/"C05-var03-config-resource-v1.0.0"
    prior=HERE.parent/"C05-var03-config-resource-v1.0.1"
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
        "priority_draft_inventory":prior/"review/excluded-priority-draft/inventory.json",
        "physical_ledger_draft_inventory":prior/"review/excluded-physical-ledger-draft/inventory.json",
        "physical_ledger_draft_validator":prior/"review/excluded-physical-ledger-draft/validate_native_cli.py",
        "physical_ledger_draft_manifest":prior/"review/excluded-physical-ledger-draft/prelaunch-manifest.json",
        "v101_contract":prior/"contract.json",
        "v101_runner":prior/"run_native_ssh.ps1",
        "v101_source_inventory":prior/"prelaunch-manifest.json",
        "v101_ssh_preflight_failure":prior/"review/root-ssh-preflight-failure-20261007.json",
        "v101_independent_preflight_no_go":prior/"review/independent-ssh-preflight-no-go-2026-10-07.md",
        "v101_encoding_probe_result":prior/"review/root-ssh5-encoding-probe-20261007.json",
        "v101_encoding_probe_script":prior/"review/root-ssh5-encoding-probe-20261007.ps1",
        "installed_exe":Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"),
        "installed_manual":Path(contract["installed_sources"]["manual_pdf"]["path"]),
        "installed_dictionary":Path(contract["installed_sources"]["dictionary"]["path"]),
        "python":Path(r"C:\Users\user\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"),
    }
    for filename in ("build.py","crew-input.json","radio-input.json","exact-diff.json",
                     "check_roundtrip.py","validate_native_cli.py"):
        paths["priority_draft_"+filename.replace(".","_").replace("-","_")]=prior/"review/excluded-priority-draft"/filename
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
    for key,tag in (("v101_contract","v101_contract"),("v101_runner","v101_runner"),
                    ("v101_source_inventory","v101_source_inventory"),
                    ("v101_ssh_preflight_failure","ssh_preflight_failure"),
                    ("v101_independent_preflight_no_go","independent_preflight_no_go"),
                    ("v101_encoding_probe_result","ssh5_encoding_probe")):
        pin=contract["excluded_v101_preflight"][tag]
        assert by_key[key]["sha256"]==pin["sha256"] and by_key[key]["bytes"]==pin["bytes"]
    assert by_key["v101_encoding_probe_script"]["sha256"]=="022ce93778670646719a2ad776322459db3b9ca2f9ba2e339836d530934e29c7"
    assert by_key["v101_encoding_probe_script"]["bytes"]==1743
    return {"schema":"c05-var03-v102-prelaunch-manifest/v1","contract_sha256":CONTRACT_SHA,
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
