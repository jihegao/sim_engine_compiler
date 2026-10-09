"""Exact prospective 115-line, 107-clock B04 child event oracle."""
from __future__ import annotations

from pathlib import Path
from model_common import HERE, LOG_PIN, exact

def semantic(raw: bytes) -> dict[str,object]:
    expected=exact(HERE/"preserved-design/expected-model.log",LOG_PIN)
    assert raw==expected, "physical event transcript differs from frozen prospective arm"
    assert len(raw)==9108 and raw.endswith(b"\r\n") and raw.count(b"\r\n")==raw.count(b"\n")==115
    lines=raw.decode("utf-8").splitlines()
    timed=[line for line in lines if line.startswith("Time: ")]
    assert len(lines)==115 and len(timed)==107
    assert "planned to last for 1 hours" in lines[46]
    assert "planned to last for 1.5 hours" in lines[101]
    return {"physical_lines":115,"timed_lines":107,"parent_first_turnround_unchanged":True,
            "second_turnround_hours":1.5,"same_time_change_marker":False}

def verify_file(path: Path) -> dict[str,object]:
    ledger=semantic(path.read_bytes())
    return {"schema":"i05-var07-physical-ledger/v101","passed":True,**ledger,"native_calls":0}
