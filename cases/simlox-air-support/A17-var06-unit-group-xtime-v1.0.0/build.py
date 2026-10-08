"""Read-only reconstruction of the single-cell A17.var06 source and export oracles."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from model_common import HERE, INPUT_SHA, EXPORT_SHA, LOG_SHA, count_model, strict_json
from report_oracle import expected_report

PARENT = HERE.parent / "A17-multi-unit-group-v1.0.0"
PARENT_INPUT = PARENT / "native-input.json"
PARENT_EXPORT = PARENT / "runs/a17-v100-ssh-20260929-01/roundtrip-raw.json"
PARENT_LOG = PARENT / "runs/a17-v100-ssh-20260929-01/model.log"


def pinned(path: Path, size: int, sha: str) -> bytes:
    body = path.read_bytes()
    assert len(body) == size and hashlib.sha256(body).hexdigest() == sha, path
    return body


def verify() -> dict:
    authored = pinned(PARENT_INPUT, 43061, "66d3eef1e1cf42d26971af9719feb68e7ec3ecd4ed188a8477f8cbe0918bb974")
    old = b'"TEACH-UNIT-2",\n                2,\n                0.0,\n                null'
    new = b'"TEACH-UNIT-2",\n                2,\n                1.0,\n                null'
    assert authored.count(old) == 1
    child_authored = authored.replace(old, new)
    assert pinned(HERE / "native-input.json", 43061, INPUT_SHA) == child_authored
    assert count_model(strict_json(child_authored)) == {"tables": 33, "rows": 20, "cells": 203}

    exported = pinned(PARENT_EXPORT, 59625, "819bbdd65799d20441191f41ca4a5d4df9aaf658466dd49dd952707d96943a42")
    old = b'[ "TEACH-GROUP", "TEACH-UNIT-2", 2, 0, null ]'
    new = b'[ "TEACH-GROUP", "TEACH-UNIT-2", 2, 1, null ]'
    assert exported.count(old) == 1
    child_exported = exported.replace(old, new)
    assert pinned(HERE / "child-roundtrip-oracle.json", 59625, EXPORT_SHA) == child_exported
    assert count_model(strict_json(child_exported)) == {"tables": 33, "rows": 38, "cells": 387}

    log = pinned(PARENT_LOG, 4039, LOG_SHA)
    assert pinned(HERE / "prospective-log-oracle.bytes", 4039, LOG_SHA) == log
    assert len(log.splitlines()) == 60 and sum(line.startswith(b"Time: ") for line in log.splitlines()) == 52
    report = expected_report()
    assert len(report["report"]["tables"]) == 8
    return {"schema": "a17-var06-source-build/v100", "passed": True,
            "authored_cells": 203, "exported_cells": 387, "physical_log_lines": 60,
            "report_tables": 8, "native_calls": 0, "accepted_checker_calls": 0}


if __name__ == "__main__":
    print(json.dumps(verify(), sort_keys=True))
