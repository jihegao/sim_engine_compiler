"""Exact E02.var02 prelaunch role map; root owns candidate audit and promotion."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from make_source_inventory import HERE, INVENTORY, document as inventory_document, encode
from model_common import INPUT_PIN, NATIVE_DIR, RUN_ID, seal
from source_gate import (CATALOG_CURRENT, INSTALLED, REPO, SELECTION, SELECTION_PIN,
                         EXCLUDED_CASE, EXCLUDED_INVENTORY, EXCLUDED_INVENTORY_PIN,
                         EXCLUDED_MANIFEST, EXCLUDED_MANIFEST_PIN, EXCLUDED_CUSTODY,
                         EXCLUDED_CUSTODY_PIN, exact, strict_json)

MANIFEST = HERE / "prelaunch-manifest.json"
CONTRACT_SHA = "f8de374b6f78e661d9f453b96fe701db321f94686d02fbec92b8e4095f8fea3b"
SPECIAL = {
    "run_native_ssh.ps1": "runner_script",
    "validate_native_cli.py": "behavior_validator",
    "preserved-design/contract.json": "prospective_contract",
    "execution-contract.json": "execution_binding",
    "native-input.json": "child_input",
}


def document() -> dict[str, object]:
    assert INVENTORY.read_bytes() == encode(inventory_document())
    inventory = strict_json(INVENTORY.read_bytes())
    selection = strict_json(exact(SELECTION, SELECTION_PIN))
    assert type(inventory) is dict and inventory["schema"] == "e02-var02-source-inventory/v104"
    assert selection["base"] == "7b9dc461d629e28ed6f719d6c155dad9db9dca60"
    rows = []
    for item in inventory["source_files"]:
        rows.append({"key": SPECIAL.get(item["path"], "owned:" + item["path"]),
                     "path": str(HERE / item["path"]),
                     "bytes": item["bytes"], "sha256": item["sha256"]})
    rows.append({"key": "owned:source-inventory.json", "path": str(INVENTORY), **seal(INVENTORY)})
    for item in selection["accepted_source_pairs"]:
        path = (REPO / item["path"]).resolve(strict=True)
        assert seal(path) == item["disk"]
        rows.append({"key": "accepted:" + item["path"], "path": str(path), **item["disk"]})
    for index, item in enumerate(selection["mandatory_originals"]):
        path = Path(item["path"])
        assert seal(path) == {"bytes": item["bytes"], "sha256": item["sha256"]}
        st = path.stat()
        assert st.st_mode == item["original_mode"]
        assert getattr(st, "st_file_attributes", None) == item["original_attributes"]
        rows.append({"key": f"mandatory:{index:02d}", "path": str(path),
                     "bytes": item["bytes"], "sha256": item["sha256"]})
    for name, (path, pin) in zip(("manual", "simlox-exe", "python", "dictionary"), INSTALLED, strict=True):
        assert seal(path) == pin
        rows.append({"key": "installed:" + name, "path": str(path), **pin})
    excluded_inventory = strict_json(exact(EXCLUDED_INVENTORY, EXCLUDED_INVENTORY_PIN))
    assert excluded_inventory["source_count"] == 77
    for item in excluded_inventory["source_files"]:
        path = (EXCLUDED_CASE / item["path"]).resolve(strict=True)
        assert path.is_relative_to(EXCLUDED_CASE.resolve(strict=True)) and seal(path) == {
            "bytes": item["bytes"], "sha256": item["sha256"]}
        rows.append({"key": "excluded-source:" + item["path"], "path": str(path),
                     "bytes": item["bytes"], "sha256": item["sha256"]})
    rows.append({"key": "excluded-source-inventory", "path": str(EXCLUDED_INVENTORY),
                 **EXCLUDED_INVENTORY_PIN})
    exact(EXCLUDED_MANIFEST, EXCLUDED_MANIFEST_PIN)
    rows.append({"key": "excluded-prelaunch-manifest", "path": str(EXCLUDED_MANIFEST),
                 **EXCLUDED_MANIFEST_PIN})
    excluded_custody = strict_json(exact(EXCLUDED_CUSTODY, EXCLUDED_CUSTODY_PIN))
    originals = excluded_custody["originals_after_freeze"]
    copies = excluded_custody["copies"]
    assert len(originals) == 40 and len(copies) == 26
    for index, name in enumerate(sorted(originals, key=str.casefold)):
        pin = originals[name]
        assert seal(Path(name)) == {"bytes": pin["bytes"], "sha256": pin["sha256"]}
        rows.append({"key": f"excluded-failed-original:{index:02d}", "path": name,
                     "bytes": pin["bytes"], "sha256": pin["sha256"]})
    for index, name in enumerate(sorted(copies, key=str.casefold)):
        pin = copies[name]
        path = Path(excluded_custody["diagnostic_copy"]) / name
        assert seal(path) == {"bytes": pin["bytes"], "sha256": pin["sha256"]}
        rows.append({"key": f"excluded-diagnostic-copy:{index:02d}", "path": str(path),
                     "bytes": pin["bytes"], "sha256": pin["sha256"]})
    rows.append({"key": "excluded-failure-custody", "path": str(EXCLUDED_CUSTODY),
                 **EXCLUDED_CUSTODY_PIN})
    assert len(rows) == inventory["source_count"] + 1 + 39 + 42 + 4 + 79 + 40 + 26 + 1
    folded = [item["key"].casefold() for item in rows]
    assert len(folded) == len(set(folded))
    for rel, key in SPECIAL.items():
        matches = [item for item in rows if item["key"] == key]
        assert len(matches) == 1 and matches[0]["path"] == str(HERE / rel)
    by_identity: dict[str, tuple[int, str]] = {}
    for item in rows:
        identity = str(Path(item["path"]).resolve(strict=True)).replace("/", "\\").casefold()
        pin = (item["bytes"], item["sha256"])
        assert by_identity.setdefault(identity, pin) == pin, "aliased source roles disagree"
    binding = strict_json((HERE / "execution-contract.json").read_bytes())
    assert binding["native_run_directory"] == str(NATIVE_DIR)
    assert binding["file_line_ascii_bytes"] == 119
    input_line = "Input file: " + str(NATIVE_DIR / "model.sxi")
    output_line = "Output file: " + str(NATIVE_DIR / "model.sxo")
    file_line = "File: " + str(NATIVE_DIR / "model.sxi").replace("\\", "/")
    assert all(x.isascii() for x in (input_line, output_line, file_line))
    assert list(map(lambda x: len(x.encode("ascii")), (input_line, output_line, file_line))) == [125, 126, 119]
    if MANIFEST.exists():
        current = strict_json(MANIFEST.read_bytes())["live_catalog_prelaunch_pin"]
        assert current["path"] == str(CATALOG_CURRENT)
    else:
        current = {"path": str(CATALOG_CURRENT), **seal(CATALOG_CURRENT)}
    return {"schema": "e02-var02-prelaunch-manifest/v104", "run_id": RUN_ID,
            "native_run_directory": str(NATIVE_DIR), "file_line_ascii_bytes": 119,
            "file_line_ascii_max": 199, "base_commit": selection["base"],
            "contract_sha256": CONTRACT_SHA,
            "execution_binding_sha256": seal(HERE / "execution-contract.json")["sha256"],
            "input_sha256": INPUT_PIN["sha256"],
            "source_inventory_sha256": seal(INVENTORY)["sha256"],
            "runner_sha256": seal(HERE / "run_native_ssh.ps1")["sha256"],
            "validator_sha256": seal(HERE / "validate_native_cli.py")["sha256"],
            "independent_reader_sha256": seal(HERE / "review/independent_reader.py")["sha256"],
            "source_count": len(rows), "source_files": rows,
            "owned_source_count": inventory["source_count"] + 1,
            "accepted_source_pair_count": 39, "required_local_source_count": 0,
            "mandatory_original_count": 42, "archived_catalog_count": 2,
            "excluded_source_count": 79, "excluded_failed_original_count": 40,
            "excluded_diagnostic_copy_count": 26, "excluded_custody_receipt_count": 1,
            "converter_negative_original_count": 0,
            "installed_executable_count": 4, "catalog_prefix_entries": 503,
            "live_catalog_prelaunch_pin": current,
            "pure_tools": ["build.py", "source_gate.py", "self_check.py",
                           "make_source_inventory.py", "make_prelaunch_manifest.py"],
            "stages": ["import", "export", "check_import_export", "calc", "jsonreport", "check_behavior"],
            "native_commands": 4, "pure_checkers": 2,
            "new_native_runs_authorized_by_manifest": 0,
            "independent_method_state": "METHOD_ONLY_NO_NATIVE_APPROVAL"}


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
        with MANIFEST.open("xb") as stream:
            stream.write(body)
    else:
        assert MANIFEST.read_bytes() == body
    print(json.dumps({"schema": "e02-var02-prelaunch-manifest-check/v104",
                      "passed": True, "source_count": document()["source_count"],
                      "sha256": hashlib.sha256(body).hexdigest()}, sort_keys=True))


if __name__ == "__main__":
    main()
