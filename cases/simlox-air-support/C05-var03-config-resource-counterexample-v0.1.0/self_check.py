"""In-memory negative checks for the retrospective oracle; sealed inputs stay read-only."""
from __future__ import annotations

from check_reclassification import Gate, RUN, check_trace
from report_oracle import build_expected, equal_cell, timed_blocks


def main() -> None:
    expected, _ = build_expected("crew", RUN / "model.log")
    blocks = timed_blocks(RUN / "model.log")
    probes = 0

    def reject(actual, want, field):
        nonlocal probes
        assert not equal_cell(actual, want, field)
        probes += 1

    reject(1, expected["ResourceResults"][34][3], "NRMA")
    reject(None, expected["ResourceResults"][34][3], "NRMA")
    reject(0, None, "SYDT")
    reject(1, 0, "NBO")
    reject("changed", expected["ProblemDescription"][0][0], "PDESC")
    reject(0.25, 0.0, "NRMO")

    for old, new in (("[MISSION-CREW 0]", "[MISSION-CREW 1]"),
                     ("allocated to mission assigned: 1", "allocated to mission assigned: 2"),
                     ("mission completed:", "mission halted:")):
        changed = [(t, text.replace(old, new)) for t, text in blocks]
        gate = Gate()
        check_trace(gate, changed)
        assert gate.failures, f"event mutation escaped: {old}"
        probes += 1

    print(f"self-check PASS: {probes} in-memory negative probes")


if __name__ == "__main__":
    main()
