"""Predeclare complete lexical witnesses for the finite prospective log arms.

The witnesses are predictions, not observations of a shared-base two-unit run.
"""

from __future__ import annotations

import hashlib
import itertools
import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
PARENT = REPO / "cases/simlox-air-support/A17-multi-unit-group-v1.0.0/runs/a17-v100-ssh-20260929-01/model.log"
PARENT_SHA = "ae6c8430c26490c16e98f7ea66a0137ea7bcd1e309c1f2ba46a44940a0e7f33e"
UNIT2_LINES = {7, 8, 17, 54, 57}
CONTROLLER1_LINES = {38, 51, 55, 56, 58}


def digest(path: Path) -> dict:
    b = path.read_bytes()
    return {"path": str(path), "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()}


def main() -> None:
    assert digest(PARENT)["sha256"] == PARENT_SHA
    source = PARENT.read_bytes()
    assert source.count(b"\r\n") == 60 and source.endswith(b"\r\n")
    lines = source.decode("utf-8-sig").splitlines()
    assert len(lines) == 60
    assert sum(x.startswith("Time:") for x in lines) == 52
    assert {i for i, line in enumerate(lines, 1) if "BASE-02" in line} == UNIT2_LINES | CONTROLLER1_LINES
    for i in UNIT2_LINES:
        assert "<BASE-02,0>" in lines[i - 1] and "<TEACH-AIR-01,BASE-02,0>" not in lines[i - 1]
    for i in CONTROLLER1_LINES:
        assert "<TEACH-AIR-01,BASE-02,0>" in lines[i - 1]
    assert lines[0] == "SIMLOX LOG FILE" and lines[1] == "36"

    forms = []
    for unit_index, controller_index, return_order in itertools.product((0, 1), (0, 1), ((0, 1), (1, 0))):
        candidate = list(lines)
        for i in UNIT2_LINES:
            candidate[i - 1] = candidate[i - 1].replace("<BASE-02,0>", f"<BASE-01,{unit_index}>")
        for i in CONTROLLER1_LINES:
            candidate[i - 1] = candidate[i - 1].replace("<TEACH-AIR-01,BASE-02,0>", f"<TEACH-AIR-01,BASE-01,{controller_index}>")
        if return_order == (1, 0):
            candidate[39:59] = candidate[49:59] + candidate[39:49]
        assert len(candidate) == 60 and sum(x.startswith("Time:") for x in candidate) == 52
        assert not any("BASE-02" in line for line in candidate)
        encoded = ("\r\n".join(candidate) + "\r\n").encode("utf-8")
        forms.append({
            "arm_id": f"unit{unit_index}-controller{controller_index}-return{''.join(map(str, return_order))}",
            "unit2_base_instance_index": unit_index,
            "id1_base_controller_index": controller_index,
            "h10_return_block_order": list(return_order),
            "status": "PRIMARY_CONTRACT_PASS_CANDIDATE" if (unit_index, controller_index, return_order) == (0, 0, (0, 1)) else "DIAGNOSTIC_NO_GO",
            "full_lines": 60,
            "timed_lines": 52,
            "crlf_bytes": len(encoded),
            "crlf_sha256": hashlib.sha256(encoded).hexdigest(),
            "lines": candidate,
        })
    assert len(forms) == 8
    object_ = {
        "schema": "a17-var01-prospective-complete-log-forms/v1",
        "source_parent": digest(PARENT),
        "interpretation": "Finite source-bound lexical predictions. Original parent lines and A03 analogue do not establish a shared-base two-unit native printout. Only the primary arm can be a pass under this contract; seven alternatives are diagnostic NO_GO.",
        "source_bindings": {
            "unit2_Unit_STID_changed_lines": sorted(UNIT2_LINES),
            "id1_station_controller_changed_lines": sorted(CONTROLLER1_LINES),
            "source_field": "Unit[TEACH-UNIT-2].STID BASE-02→BASE-01",
            "other_parent_line_roles": "exact fixed prefix/mission/continuation text under unchanged source, hypothesized until native observation",
        },
        "full_forms": forms,
    }
    out = HERE / "complete-log-forms.json"
    assert not out.exists()
    with out.open("x", encoding="utf-8", newline="\n") as f:
        json.dump(object_, f, ensure_ascii=False, indent=2)
        f.write("\n")
    prior = json.loads((HERE / "contract-v2.json").read_text(encoding="utf-8"))
    final = dict(prior)
    final["schema"] = "a17-var01-prospective-contract/v3"
    final["complete_log_forms"] = digest(out)
    final["v2_design_history"] = digest(HERE / "contract-v2.json")
    final["log_oracle_completeness"] = "The partial-order ledger and all 60 lexical line positions are now closed before native observation. The lines are hypotheses, not established native outputs for this configuration."
    path = HERE / "contract-v3.json"
    assert not path.exists()
    with path.open("x", encoding="utf-8", newline="\n") as f:
        json.dump(final, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(json.dumps({"contract": digest(path), "full_log_forms": digest(out), "forms": len(forms)}, sort_keys=True))


if __name__ == "__main__":
    main()
