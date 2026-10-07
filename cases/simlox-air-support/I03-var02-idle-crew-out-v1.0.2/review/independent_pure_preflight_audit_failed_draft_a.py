"""Read-only exact-byte audit of the I03.var02 v102 final source freeze."""

import hashlib
import json
from collections import Counter
from pathlib import Path

import independent_replay_v3 as independent


HERE = Path(__file__).resolve().parent.parent
MANIFEST = HERE / "prelaunch-manifest-v2.json"
MANIFEST_SHA = "fa803d4b0dc7746e4ae3e72288dcdb2cc1a3d3334ca6e5adcb2df8fcb2de1da6"
RUN_ID = "i03-var02-idle-out-v102-ssh-20261007-01"
ROLES = {
    "child_contract": ("contract.json", "1f058ae8706d4de81c28099b6580619eb4cb879e20314619f387839d9150ee29"),
    "child_input": ("native-input.json", "b6cebc1b3a44e6bd462e222690e90026e8336e1ad55f0b68b2d9212c635176b4"),
    "runner_script": ("run_native_ssh_v3.ps1", "c5c117363458ffa38d61bc4296c07cdd5dc0b536953385e36a00c9e5570f5953"),
    "behavior_validator": ("validate_native_cli.py", "bb3ed0d380c86b6ded4ec85751084c03c9e45fcc60c8ee90b9ae64633218fc"),
    "independent_replay": ("review/independent_replay_v3.py", "e8a249c11df2f90f08e838f854432a27eeffacae5b814ceeb16ab4c00ad27e6e"),
    "independent_self_check": ("review/independent_self_check_v3.py", "46b09155540c59de9369b26f4f6258d4c079e6cb75710dbd841bd075a35d73ae"),
}


def pin(path: Path) -> dict:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def main() -> None:
    assert pin(MANIFEST) == {"bytes": 66992, "sha256": MANIFEST_SHA}
    doc = independent.native_json(MANIFEST.read_bytes())
    assert doc["schema"] == "i03-var02-v102-prelaunch-manifest/v2"
    assert doc["run_id"] == RUN_ID and doc["native_runs_authorized_by_manifest"] == 0
    entries = doc["source_files"]
    assert type(entries) is list and type(doc["source_count"]) is int
    assert len(entries) == doc["source_count"] == 179
    assert len({e["key"] for e in entries}) == 179
    counts = Counter()
    for e in entries:
        assert set(e) == {"key", "path", "bytes", "sha256"}
        assert type(e["key"]) is str and type(e["path"]) is str
        assert type(e["bytes"]) is int and e["bytes"] >= 0
        assert type(e["sha256"]) is str and len(e["sha256"]) == 64
        path = Path(e["path"])
        assert path.is_absolute() and path.is_file(), (e["key"], path)
        assert pin(path) == {"bytes": e["bytes"], "sha256": e["sha256"]}, e["key"]
        counts[e["key"].split(":", 1)[0]] += 1
    by_key = {e["key"]: e for e in entries}
    for key, (relative, sha) in ROLES.items():
        e = by_key[key]
        assert Path(e["path"]).resolve() == (HERE / relative).resolve()
        assert e["sha256"] == sha
    assert counts["accepted_source_local"] == 20 and counts["accepted_run"] == 34
    assert counts["installed"] == 3 and counts["independent_replay"] == 1
    assert counts["independent_self_check"] == 1 and counts["catalog_live_prelaunch"] == 1
    assert by_key["child_contract"]["sha256"] == doc["contract_sha256"]
    assert not (HERE / "runs" / RUN_ID).exists()
    contract = independent.native_json((HERE / "contract.json").read_bytes())
    a = independent.Audit()
    independent.source_pins(contract, a)
    runner = (HERE / "run_native_ssh_v3.ps1").read_text(encoding="utf-8-sig")
    assert runner.count("review\\independent_replay_v3.py") == 2
    assert "review\\independent_replay_v2.py" not in runner
    assert "Stop-Process" not in runner and "-WindowStyle Hidden" in runner
    assert "prelaunch-manifest-v2.json" in runner
    assert "i03-var02-v102-prelaunch-manifest/v2" in runner
    assert "if (Test-Path -LiteralPath $run) { throw 'reserved run path already exists' }" in runner
    print(json.dumps({"schema": "i03-var02-independent-pure-preflight-audit/v1",
                      "decision": "GO_PURE_PREFLIGHT_SOURCE_BYTES_ONLY",
                      "manifest_sha256": MANIFEST_SHA,
                      "source_pins": len(entries), "contract_checks": a.checks,
                      "accepted_source_pairs": 20, "accepted_run_records": 34,
                      "run_absent": True}, sort_keys=True))


if __name__ == "__main__":
    main()
