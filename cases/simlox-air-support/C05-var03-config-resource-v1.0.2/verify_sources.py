"""Read-only accepted local/Git/manual/native seal verifier for SSH preflight."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
CONTRACT_SHA = "b397b217fbf19ec9b6ae9a166a7b3124144f7ec74680675b1fc47b3b69469d0f"
GO_SHA = "e83e8584bcee37fd3fe8b69646202ed25d31defc78151e24e6689421d6ae4b93"
CORRECTION_SHA = "487ecae15d6a3e66ff6f966be937d2895d6925632306466723f00c43af097813"


def identity(path: Path) -> dict:
    data=path.read_bytes()
    return {"bytes":len(data),"sha256":hashlib.sha256(data).hexdigest()}


def same(path: Path,pin: dict) -> bool:
    return identity(path)=={"bytes":pin["bytes"],"sha256":pin["sha256"]}


def verify() -> dict:
    contract_path=HERE/"contract.json"
    assert identity(contract_path)["sha256"]==CONTRACT_SHA
    contract=json.loads(contract_path.read_text(encoding="utf-8-sig"))
    assert identity(HERE/"review/independent-contract-go-2026-10-07.md")["sha256"]==GO_SHA
    assert identity(HERE.parent/"C05-var03-config-resource-v1.0.0/review/independent-contract-factual-correction-2026-10-07.md")["sha256"]==CORRECTION_SHA
    assert contract["base_commit"]=="1aa2fa8ce746c3b6f03097be3d090faffe106f46"
    tested=0
    for package in contract["accepted_source_pins"].values():
        for relative,pins in package["files"].items():
            source=HERE.parent/package["package"]/relative
            assert same(source,pins["local"]),f"local source {source}"
            repo_relative=source.relative_to(ROOT).as_posix()
            git=subprocess.run(["git","show",f"{contract['base_commit']}:{repo_relative}"],cwd=ROOT,
                               stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True).stdout
            assert {"bytes":len(git),"sha256":hashlib.sha256(git).hexdigest()}==pins["published_git"],f"published Git source {repo_relative}"
            tested+=1
    assert tested==23
    raw_count=0
    for key,pin in contract["accepted_native_runs"].items():
        run=Path(pin["path"])
        assert same(run/"closure.json",pin["closure"]),f"{key} closure"
        assert same(run/"invocation.json",pin["invocation"]),f"{key} invocation"
        closure=json.loads((run/"closure.json").read_text(encoding="utf-8-sig"))
        assert closure["run_id"]==pin["run_id"] and closure["raw"]==pin["raw"]
        assert closure["invocation_sha256"]==pin["invocation"]["sha256"]
        for name,seal in pin["raw"].items():
            assert same(run/name,seal),f"{key}/{name}"
            raw_count+=1
    assert raw_count==48
    excluded=contract["excluded_diagnostic"]
    for name in ("frozen_contract","initial_go_memo","no_go_addendum","draft_inventory"):
        pin=excluded[name]
        assert same(ROOT/pin["path"],pin),f"excluded {name}"
    v101=contract["excluded_v101_preflight"]
    for name in ("v101_contract","v101_runner","v101_source_inventory",
                 "ssh_preflight_failure","independent_preflight_no_go","ssh5_encoding_probe"):
        pin=v101[name]
        assert same(ROOT/pin["path"],pin),f"excluded v101 {name}"
    prior_manifest=json.loads((ROOT/v101["v101_source_inventory"]["path"]).read_text(encoding="utf-8-sig"))
    assert len(prior_manifest["source_files"])==v101["v101_source_inventory"]["source_pins"]==70
    for pin in prior_manifest["source_files"]:
        assert same(Path(pin["path"]),pin),f"excluded v101 source inventory {pin['key']}"
    probe=HERE.parent/"C05-var03-config-resource-v1.0.1/review/root-ssh5-encoding-probe-20261007.ps1"
    assert same(probe,{"bytes":1743,"sha256":"022ce93778670646719a2ad776322459db3b9ca2f9ba2e339836d530934e29c7"})
    for name in ("manual_pdf","dictionary"):
        pin=contract["installed_sources"][name]
        assert identity(Path(pin["path"]))["sha256"]==pin["sha256"],f"installed {name}"
    assert identity(Path(r"C:\Program Files\Systecon\SIMLOX\Simlox.exe"))["sha256"]==(
        "fe24c5bffc0c0641894bb335484cfb83993e3db2bd60122ddadfedd39a8c4db0")
    return {"schema":"c05-var03-v102-source-verification/v1","passed":True,
            "accepted_local_and_git_files":tested,"accepted_raw_seals":raw_count,
            "excluded_contract_artifacts":4,"excluded_v101_artifacts":7,
            "excluded_v101_source_pins":70,"installed_manual_dictionary":2}


if __name__=="__main__":
    print(json.dumps(verify(),indent=2))
