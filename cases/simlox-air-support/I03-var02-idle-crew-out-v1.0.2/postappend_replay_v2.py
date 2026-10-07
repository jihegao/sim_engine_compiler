"""Read-only check of reviewer verdict across the authorized catalog append.

The reviewer source is frozen. Its sole conditional count is the exact
whole-file catalog pin applied only while the live catalog has 490 entries.
All model, source, raw, report and typed ledger checks remain mandatory.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess
import sys

from postappend_context_v2 import check as check_context
from postrun_audit import audit as author_audit
from verify_sources import HERE, REPO, strict_equal, verify


MANIFEST = HERE / "prelaunch-manifest-v2.json"
REVIEWER = HERE / "review/independent_replay_v3.py"
SAVED = HERE / "review/independent-postrun-verdict-v3.json"
INDEX_V1 = HERE / "evidence-index.json"
V1_INDEX_SHA = "57d5ebba2f372f7f07ef092e5c2de58a5577988ade19587f13e522e3706339d8"
REVIEWER_SHA = "e8a249c11df2f90f08e838f854432a27eeffacae5b814ceeb16ab4c00ad27e6e"
SAVED_SHA = "67265c50b84e1ea1c325914e5ecd4988e58a2548e1fbe02b4ca2340d143a13c6"
NO_GO_SHA = "80ed62c97198b8440e517e0c6f0b9e14ca3eb0f9264fff7658b6a68abb168abe"
NO_GO_AUDIT_SHA = "8613c5eb5a2dd0987eff06b41334ab7fab53af8a66ce37dc66c37cfd63e6ef83"
FAILURE_SHA = "ca726072edaef6582fc456109b0ea630a7e922bd406f454302b0324d811551a1"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check() -> dict:
    assert sha(REVIEWER) == REVIEWER_SHA
    assert sha(SAVED) == SAVED_SHA
    assert sha(INDEX_V1) == V1_INDEX_SHA
    assert sha(HERE / "review/independent-publication-v1-no-go-2026-10-08.md") == NO_GO_SHA
    assert sha(HERE / "review/independent-publication-v1-no-go-audit.py") == NO_GO_AUDIT_SHA
    assert check_context()["historical_records"] == 8
    assert sha(HERE / "preserved-postappend-failure/i03-v102-postappend-index-failure-20261007-01/failure-receipt.json") == FAILURE_SHA
    provenance = verify("sealed", MANIFEST)
    assert provenance["passed"] and provenance["catalog"]["live_entries"] >= 491
    author = author_audit()
    assert author["decision"] == "GO_AUTHOR_SEALED_REPLAY"
    original = json.loads(SAVED.read_text(encoding="utf-8"))
    assert original["status"] == "GO_BOUNDED" and type(original["checks"]) is int and original["checks"] == 14996
    runner = subprocess.run([sys.executable, "-X", "utf8", "-B", str(REVIEWER)],
                            cwd=REPO, capture_output=True)
    assert runner.returncode == 0 and not runner.stderr, runner.stderr.decode("utf-8", "replace")
    current = json.loads(runner.stdout.decode("utf-8-sig"))
    assert current["status"] == "GO_BOUNDED" and type(current["checks"]) is int and current["checks"] == 14995
    old_other = {k: v for k, v in original.items() if k != "checks"}
    new_other = {k: v for k, v in current.items() if k != "checks"}
    assert strict_equal(old_other, new_other), "model/physical/report verdict changed"
    assert original["parent_report_cells"] == original["child_report_cells"] == 5210
    assert original["native_raw_files"] == 23 and original["native_steps"] == 6
    return {
        "schema": "i03-var02-v102-postappend-replay/v2",
        "decision": "GO_AUTHOR_POSTAPPEND_REPLAY_REPAIR",
        "independent_content_decision": "separate_review_required",
        "original_native_acceptance_checks": 14996,
        "postappend_replay_checks": 14995,
        "conditional_prepublication_catalog_check_not_applicable": 1,
        "remaining_verdict_fields_type_exact_equal": True,
        "parent_report_cells": 5210,
        "child_report_cells": 5210,
        "native_runs_added_after_original": 0,
        "original_v1_index_decision": "NO_GO_PUBLICATION_REPRO_V1",
    }


if __name__ == "__main__":
    print(json.dumps(check(), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
