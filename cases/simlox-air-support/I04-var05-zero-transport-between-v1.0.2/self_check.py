"""Pure source, export, eventwise ledger, full report, and mutation checks."""
from __future__ import annotations

import copy
import json

import build
import check_roundtrip
import event_ledger
import make_source_inventory as inventory
import report_oracle
import source_gate
from model_common import parse, read


def reject(callback):
    try:
        callback()
    except (AssertionError, ValueError, KeyError, TypeError, UnicodeError):
        return 1
    raise AssertionError("semantic mutation escaped")


def raw(lines):
    return ("\r\n".join(lines) + "\r\n").encode("utf-8")


def run():
    assert build.run(False)["native_calls"] == 0
    source = source_gate.verify("live")
    assert source["accepted_current_disk_git_pairs"] == 403
    assert source["old_v100_owned_sources"] == 130
    assert source["old_v100_prelaunch_roles"] == 1172
    assert source["excluded_v101_owned_sources"] == 172
    assert source["excluded_v101_prelaunch_roles"] == 1980
    assert source["excluded_v101_failed_preflight_originals"] == 3
    assert source["excluded_v101_pure_originals"] == 21
    assert source["excluded_v101_root_and_copier_originals"] == 18
    assert source["owned_v102_context_copies"] == 20
    assert source["inherited_parent_manifest_roles"] == 456
    assert source["mandatory_accepted_original_raw"] == 168
    assert source["failed_v100_originals"] == 34
    assert source["failed_v100_preflight_originals"] == 18
    assert source["mandatory_failed_context_originals"] == 53
    assert source["owned_failed_context_copies"] == 78
    assert source["native_run_path"]["native_run_directory"] == str(source_gate.RUN_DIR)
    assert source["native_run_path"]["file_line_ascii_bytes"] == 121
    binding = read(build.HERE / "execution-contract.json")
    assert tuple(binding["future_author_files"]) == inventory.FUTURE_AUTHOR
    assert tuple(binding["future_generated_patterns"]) == inventory.FUTURE_GENERATED
    assert tuple(binding["future_custody_files"]) == inventory.FUTURE_CUSTODY
    assert tuple(binding["future_review_prefixes"]) == inventory.FUTURE_REVIEW_PREFIXES
    assert tuple(binding["runtime_exclusions"]) == ("runs/", "test-output/", "transport-evidence/")
    export = check_roundtrip.validate(check_roundtrip.ORACLE)
    assert export["exported_cells"] == 407
    parent = report_oracle.validate(report_oracle.PARENT_RAW.read_bytes(), False)
    assert parent["cells_checked"] == 4044
    child = read(report_oracle.CHILD_ORACLE)
    assert report_oracle.validate_oracle(child, True) == 4044
    variants = event_ledger.expected_forms()
    assert len(variants) == 4
    results = [event_ledger.validate(raw(v["lines"])) for v in variants]
    assert [r["lines"] for r in results] == [118, 120, 119, 121]
    assert [r["timed_lines"] for r in results] == [104, 105, 105, 106]
    assert all(r["physical"]["target_ready_terminal"] == 2 for r in results)
    base = variants[0]["lines"]
    negatives = 0
    for start, replacement in (
        ("Time: 10.5 <TEACH-UNIT-2", "Time: 11 <TEACH-UNIT-2"),
        ("system transfered out: <TEACH-AIR-01,0>", "system transfered out: <TEACH-AIR-01,1>"),
        ("<BASE-01,0>> system transfered out", "<BASE-02,0>> system transfered out"),
        ("nbr ready increased at unit: <TEACH-UNIT-2", "nbr ready increased at unit: <TEACH-UNIT"),
        ("Time: 19 <BASIC-MISSION", "Time: 19.5 <BASIC-MISSION"),
    ):
        changed = [line.replace(start, replacement, 1) for line in base]
        assert changed != base
        negatives += reject(lambda x=changed: event_ledger.validate(raw(x)))
    for changed in (
        base[:61] + [base[61]] + base[61:],
        base[:61] + ["Time: 10.5 unrecognized event"] + base[61:],
        base[:61] + [variants[2]["lines"][61]] * 2 + base[61:],
        base[:60] + [base[61]] + base[60:61] + base[62:],
    ):
        negatives += reject(lambda x=changed: event_ledger.validate(raw(x)))
    changed = copy.deepcopy(child)
    changed["report"]["tables"][2]["instances"][0]["rows"][21][4] = 1
    negatives += reject(lambda: report_oracle.compare(changed, child))
    negatives += reject(lambda: report_oracle.validate_oracle(changed, True))
    changed = copy.deepcopy(child)
    changed["report"]["tables"][0]["columns"][0]["key"] = True
    negatives += reject(lambda: report_oracle.compare(changed, child))
    changed = copy.deepcopy(child)
    changed["report"]["tables"][3]["instances"][0]["rows"][0][0] = 1.0
    negatives += reject(lambda: report_oracle.compare(changed, child))
    roundtrip = read(check_roundtrip.ORACLE)
    changed = copy.deepcopy(roundtrip)
    changed["model"]["tables"][17]["instances"][0]["rows"][0][5] = 0.5
    negatives += reject(lambda: check_roundtrip.compare(changed, roundtrip))
    changed = copy.deepcopy(roundtrip)
    changed["model"]["tables"][17]["columns"][0]["key"] = not changed["model"]["tables"][17]["columns"][0]["key"]
    negatives += reject(lambda: check_roundtrip.compare(changed, roundtrip))
    negatives += reject(lambda: parse(b'{"x":1,"x":1}'))
    negatives += reject(lambda: parse(b'{"x":1e999}'))
    assert inventory.allowed_future("README-publication.md")
    assert inventory.allowed_future("preserved-postrun/postrun-000.bytes")
    assert inventory.allowed_future("review/independent-content-go-2026-10-08.md")
    assert not inventory.allowed_future("review/independent-content-x/nested.py")
    assert not inventory.allowed_future("preserved-postrun/runs/omitted.py")
    assert not inventory.allowed_future("unknown-published.py")
    assert negatives == 17
    return {"schema": "i04-var05-pure-self-check/v102", "source_pairs": 403,
            "old_v100_owned_sources": 130, "old_v100_prelaunch_roles": 1172,
            "excluded_v101_owned_sources": 172, "excluded_v101_prelaunch_roles": 1980,
            "excluded_v101_failed_preflight_originals": 3,
            "excluded_v101_pure_originals": 21,
            "excluded_v101_root_and_copier_originals": 18,
            "owned_v102_context_copies": 20,
            "inherited_parent_roles": 456, "accepted_raw": 168,
            "failed_raw": 34, "failed_preflight_originals": 18, "export_cells": 407,
            "accepted_parent_cells": 4044, "prospective_child_cells": 4044,
            "positive_log_forms": 4, "semantic_mutations_rejected": negatives, "native_calls": 0}


if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True))
