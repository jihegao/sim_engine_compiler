"""Deterministic source map. Root alone writes the canonical manifest once."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import sys

from make_source_inventory import HERE, body as inventory_body, candidate as inventory_candidate
from source_gate import REPO, RUN_ID, check, pin, unique_json, verify

SCHEMA = "i03-var05-in-zero-prelaunch-manifest/v1"
DESIGN_SHA = "95ba77bcac344e023f140a39b4f88b4f94160d07c2a4e94563ff84de592f7331"
ROLE = {
    "contract.json": "child_contract",
    "execution-contract.json": "execution_binding",
    "native-input.json": "child_input",
    "validate_native_cli.py": "behavior_validator",
    "run_native_ssh.ps1": "runner_script",
    "review/independent_replay.py": "independent_replay",
    "review/independent_self_check.py": "independent_self_check",
}


def candidate(*, provisional: bool = False, mode: str = "sealed") -> dict:
    assert mode in ("live", "sealed")
    verified = verify(mode)
    assert verified["counts"] == {"source_pairs": 80, "accepted_original_raw": 112,
                                  "required_docs": 8, "installed": 3}
    design = unique_json((HERE / "contract.json").read_bytes())
    source = design["source_lineage"]
    entries = []
    keys: set[str] = set()
    paths: set[str] = set()

    def add(key: str, path: Path, wanted: dict | None = None) -> None:
        absolute = path.resolve(strict=True)
        identity = str(absolute).lower()
        assert key not in keys and identity not in paths, (key, absolute)
        keys.add(key)
        paths.add(identity)
        got = pin(absolute.read_bytes())
        if wanted is not None:
            assert got == {name: wanted[name] for name in ("bytes", "sha256")}, (key, got, wanted)
        entries.append({"key": key, "path": str(absolute), **got})

    owned = inventory_candidate(provisional=provisional)
    for row in owned["source_files"]:
        key = ROLE.get(row["relative_path"], "owned:" + row["relative_path"])
        add(key, Path(row["path"]), row)
    if not provisional:
        inventory = HERE / "source-inventory.json"
        exact = inventory_body(owned)
        assert inventory.read_bytes() == exact
        add("owned_source_inventory", inventory)
    for index, row in enumerate(source["accepted_parent"]["all_source_refs"] +
                                source["accepted_prerequisites"]["all_source_refs"]):
        add(f"accepted_source:{index}", REPO / row["path"], row["disk"])
    for index, row in enumerate(source["mandatory_original_raw"]):
        add(f"accepted_raw:{index}", Path(row["path"]), row)
    for index, (relative, row) in enumerate(source["required_docs"].items()):
        path = REPO / relative
        if str(path.resolve(strict=True)).lower() not in paths:
            add(f"required_doc:{index}", path, row)
        else:
            check(path, row)
    for field in ("installed_manual", "installed_dictionary", "installed_executable"):
        row = source[field]
        add("installed:" + field, Path(row["path"]), row)
    ancestry = REPO / "cases/simlox-air-support/I03-var11-out-unarrived-horizon-v1.0.0/captured_process.ps1"
    if str(ancestry.resolve(strict=True)).lower() not in paths:
        add("accepted_capture_helper_ancestry", ancestry,
            {"bytes": (HERE / "captured_process.ps1").stat().st_size,
             "sha256": "17285b90093c2d80c6241e1345b9926a2e4dd0f0b2b24f831c84c1cfa885b794"})
    binding = pin((HERE / "execution-contract.json").read_bytes())
    assert design["run_id_proposed_absent"] == RUN_ID
    return {"schema": SCHEMA, "run_id": RUN_ID, "contract_sha256": DESIGN_SHA,
            "execution_binding_sha256": binding["sha256"],
            "source_count": len(entries), "source_files": entries,
            "live_catalog_prelaunch_pin": {
                "path": str((REPO / "cases/simlox-air-support/publication-index-v1.json").resolve(strict=True)),
                **source["catalog_local_point_time"]},
            "historical_catalog_prefix_always_checked": 494,
            "accepted_raw_records": 112, "accepted_nonclosure_raw": 101,
            "accepted_closure_records": 7, "accepted_invocation_records": 4,
            "new_native_runs_authorized_by_manifest": 0,
            "independent_method_state": "provisional" if provisional else "exact methods pinned; fresh approval required"}


def body(data: dict) -> bytes:
    return (json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def main() -> None:
    args = sys.argv[1:]
    assert args in ([], ["--dry"], ["--provisional"], ["--write"])
    provisional = args == ["--provisional"]
    mode = "live" if args in (["--write"], ["--provisional"]) else "sealed"
    data = body(candidate(provisional=provisional, mode=mode))
    output = HERE / "prelaunch-manifest.json"
    if args == ["--write"]:
        assert not output.exists(), "canonical prelaunch manifest already exists"
        output.write_bytes(data)
    elif args == []:
        assert output.is_file() and output.read_bytes() == data
    print(json.dumps({"schema": "i03-var05-manifest-check/v1", "source_count": json.loads(data)["source_count"],
                      "manifest_sha256": hashlib.sha256(data).hexdigest(),
                      "written": args == ["--write"], "provisional": provisional, "mode": mode}, sort_keys=True))


if __name__ == "__main__":
    main()
