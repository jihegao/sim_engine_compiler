"""Build the exact prelaunch source-role map; candidate and write are absent-only."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from make_source_inventory import HERE, INVENTORY, encode as encode_json, document as inventory_document
from model_common import INPUT_SHA, NATIVE_DIR, RUN_ID, seal
from source_gate import (PAIRS, PINS, REPO, SELECTION, PARENT_CATALOG,
                         CONVERTER_NEGATIVE, CONVERTER_NEGATIVE_PIN)
from source_gate import INSTALLED_EXE, INSTALLED_EXE_PIN, PYTHON_RUNTIME, PYTHON_RUNTIME_PIN

MANIFEST = HERE / "prelaunch-manifest.json"
CONTRACT_SHA = "58c12480998f691b619f305922eace2eb1b4aede71fbb779de77ad0085bb15e7"
RUNNER = HERE / "run_native_ssh.ps1"
VALIDATOR = HERE / "validate_native_cli.py"
READER = HERE / "review/independent_reader.py"
SPECIAL = {"run_native_ssh.ps1": "runner_script", "validate_native_cli.py": "behavior_validator",
           "preserved-design/contract.json": "prospective_contract", "execution-contract.json": "execution_binding",
           "native-input.json": "child_input"}


def assert_special_roles(rows: list[dict]) -> None:
    for rel, key in SPECIAL.items():
        matches = [row for row in rows if row["key"] == key]
        assert len(matches) == 1 and matches[0]["path"] == str(HERE / rel)
    keys = [row["key"] for row in rows]
    assert len(keys) == len({key.casefold() for key in keys})


def document() -> dict:
    assert INVENTORY.read_bytes() == encode_json(inventory_document())
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    pins = json.loads(PINS.read_text(encoding="utf-8"))
    pairs = json.loads(PAIRS.read_text(encoding="utf-8"))
    selection = json.loads(SELECTION.read_text(encoding="utf-8"))
    assert len(pairs) == 59 and len(pins["mandatory_originals"]) == 66
    assert selection["base"] == "270740a51e937be00b6975ab2960c16ccb131f5a"
    source_files = []
    for row in inventory["source_files"]:
        source_files.append({"key": SPECIAL.get(row["path"], "owned:" + row["path"]),
                             "path": str(HERE / row["path"]),
                             "bytes": row["bytes"], "sha256": row["sha256"]})
    source_files.append({"key": "owned:source-inventory.json", "path": str(INVENTORY), **seal(INVENTORY)})
    for row in pairs:
        path = REPO / row["path"]
        assert seal(path) == row["disk"]
        source_files.append({"key": "accepted:" + row["path"], "path": str(path), **row["disk"]})
    for index, row in enumerate(pins["required_local_sources"]):
        path = Path(row["path"])
        assert seal(path) == {"bytes": row["bytes"], "sha256": row["sha256"]}
        source_files.append({"key": f"required-local:{index:02d}", "path": str(path),
                             "bytes": row["bytes"], "sha256": row["sha256"]})
    for index, row in enumerate(pins["mandatory_originals"]):
        path = Path(row["path"])
        assert seal(path) == {"bytes": row["bytes"], "sha256": row["sha256"]}
        source_files.append({"key": f"mandatory:{index:02d}", "path": str(path),
                             "bytes": row["bytes"], "sha256": row["sha256"]})
    for label in ("catalog_local_502", "catalog_git_502"):
        row = pins[label]
        path = Path(row["path"])
        assert seal(path) == {"bytes": row["bytes"], "sha256": row["sha256"]}
        source_files.append({"key": "archive:" + label, "path": str(path),
                             "bytes": row["bytes"], "sha256": row["sha256"]})
    assert seal(CONVERTER_NEGATIVE) == CONVERTER_NEGATIVE_PIN
    source_files.append({"key": "converter:failed-file-line-v100", "path": str(CONVERTER_NEGATIVE),
                         **CONVERTER_NEGATIVE_PIN})
    for key, path, pin in (("installed:simlox-exe", INSTALLED_EXE, INSTALLED_EXE_PIN),
                           ("installed:python-runtime", PYTHON_RUNTIME, PYTHON_RUNTIME_PIN)):
        assert seal(path) == pin
        source_files.append({"key": key, "path": str(path), **pin})
    execution = HERE / "execution-contract.json"
    binding = json.loads(execution.read_text(encoding="utf-8"))
    assert binding["native_run_directory"] == NATIVE_DIR and binding["file_line_ascii_bytes"] == 182
    settings = binding["selected_report_instrumentation"]
    assert seal(Path(settings["path"])) == {"bytes": settings["bytes"], "sha256": settings["sha256"]}
    source_files.append({"key": "instrumentation:j07-group-settings", "path": settings["path"],
                         "bytes": settings["bytes"], "sha256": settings["sha256"]})
    if MANIFEST.exists():
        prior = json.loads(MANIFEST.read_text(encoding="utf-8"))
        current = prior["live_catalog_prelaunch_pin"]
        assert current["path"] == str(PARENT_CATALOG)
    else:
        current = {"path": str(PARENT_CATALOG), **seal(PARENT_CATALOG)}
    assert_special_roles(source_files)
    by_path = {}
    for row in source_files:
        identity = (row["bytes"], row["sha256"])
        resolved = str(Path(row["path"]).resolve(strict=True)).replace("/", "\\").casefold()
        old = by_path.setdefault(resolved, identity)
        assert old == identity, "one path has conflicting role pins"
    file_line = "File: " + str(Path(NATIVE_DIR) / "model.sxi").replace("\\", "/")
    assert file_line.isascii() and len(file_line.encode("ascii")) == 182
    assert sum(row["key"] == "instrumentation:j07-group-settings" and
               row["path"] == settings["path"] and row["sha256"] == settings["sha256"]
               for row in source_files) == 1
    return {
        "schema": "a17-var06-prelaunch-manifest/v100", "run_id": RUN_ID,
        "native_run_directory": NATIVE_DIR, "file_line_ascii_bytes": 182,
        "file_line_ascii_max": 199, "base_commit": selection["base"],
        "contract_sha256": CONTRACT_SHA, "execution_binding_sha256": seal(execution)["sha256"],
        "input_sha256": INPUT_SHA, "source_inventory_sha256": seal(INVENTORY)["sha256"],
        "runner_sha256": seal(RUNNER)["sha256"], "validator_sha256": seal(VALIDATOR)["sha256"],
        "independent_reader_sha256": seal(READER)["sha256"],
        "report_settings": {"path": settings["path"], "bytes": settings["bytes"], "sha256": settings["sha256"]},
        "source_count": len(source_files), "source_files": source_files,
        "owned_source_count": inventory["source_count"] + 1,
        "accepted_source_pair_count": 59, "required_local_source_count": 12,
        "mandatory_original_count": 66, "archived_catalog_count": 2,
        "converter_negative_original_count": 1,
        "installed_executable_count": 2,
        "catalog_prefix_entries": 502, "live_catalog_prelaunch_pin": current,
        "pure_tools": ["build.py", "source_gate.py", "self_check.py",
                       "make_source_inventory.py", "make_prelaunch_manifest.py"],
        "stages": ["import", "export", "check_import_export", "calc", "selectedreport", "check_behavior"],
        "native_commands": 4, "pure_checkers": 2,
        "new_native_runs_authorized_by_manifest": 0,
        "independent_method_state": "METHOD_ONLY_NO_NATIVE_APPROVAL",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--candidate", type=Path)
    group.add_argument("--write", action="store_true")
    args = parser.parse_args()
    body = encode_json(document())
    if args.candidate is not None:
        assert args.candidate.is_absolute() and not args.candidate.is_relative_to(HERE)
        with args.candidate.open("xb") as stream:
            stream.write(body)
    elif args.write:
        with MANIFEST.open("xb") as stream:
            stream.write(body)
    else:
        assert MANIFEST.read_bytes() == body, "canonical prelaunch manifest differs"
    print(json.dumps({"schema": "a17-var06-prelaunch-manifest-check/v100", "passed": True,
                      "source_count": document()["source_count"],
                      "sha256": hashlib.sha256(body).hexdigest()}, sort_keys=True))


if __name__ == "__main__":
    main()
