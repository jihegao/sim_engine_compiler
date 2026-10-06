"""Pure static negative probes for frozen source and event gates; no native calls."""
from __future__ import annotations

import hashlib
import copy
import json
from pathlib import Path
import tempfile

from build import PARENT, PARENT_SHA, ARMS, build, changes, sha
from check_roundtrip import INPUT_SHA, check, parse, tables
from validate_native_cli import Gate, PARENT as PARENT_RUN, assert_event, expected_system, near

HERE = Path(__file__).resolve().parent


def main() -> None:
    parent = parse(PARENT)
    assert sha(PARENT.read_bytes()) == PARENT_SHA
    generated = {arm: build(parent, arm) for arm in ARMS}
    for arm, doc in generated.items():
        assert parse(HERE / f"{arm}-input.json") == doc
        assert sha((HERE / f"{arm}-input.json").read_bytes()) == INPUT_SHA[arm]
        assert len([t for t in tables(doc).values() if any(rows for _, rows in t[1])]) == 20
    with tempfile.TemporaryDirectory() as temporary:
        run = Path(temporary)
        (run / "input.json").write_bytes((HERE / "factor1-input.json").read_bytes())
        (run / "import.log").write_text("Import completed!", encoding="utf8")
        (run / "export.log").write_text("Export completed!", encoding="utf8")
        source = generated["factor1"]
        def fixture(doc):
            (run / "roundtrip-raw.json").write_text(json.dumps(doc), encoding="utf8")
            return check(run, "factor1")
        assert fixture(source)["passed"]
        for mutation in ("row", "column", "instance_name"):
            bad = copy.deepcopy(source)
            target = next(t for t in bad["model"]["tables"] if t["name"] == "Resource")
            if mutation == "row":
                target["instances"][0]["rows"][0][1] = "wrong description"
            elif mutation == "column":
                target["columns"][1]["name"] = "WRONG"
            else:
                target["instances"][0]["instance_name"] = "WRONG"
            assert not fixture(bad)["passed"], mutation
    pair = changes(generated["factor1"], generated["factor3"])
    assert len(pair) == 2 and any(x["cell"].endswith(".ARTF") for x in pair)
    # One-byte source tamper must invalidate the sealed source identity.
    tampered = bytearray((HERE / "factor1-input.json").read_bytes())
    tampered[-2] = ord(" ")
    assert hashlib.sha256(tampered).hexdigest() != INPUT_SHA["factor1"]
    lines = (PARENT_RUN / "model.log").read_text(encoding="utf-8-sig").splitlines()
    good = Gate()
    assert_event(good, lines, 8 + 1/6, "mission starting, duration: 1", 1, "parent launch")
    assert not good.failures
    # Timing mutation is caught at the exact physical launch gate.
    bad_timing = [line.replace("Time: 8.16667", "Time: 8.2") if "mission starting, duration: 1" in line else line for line in lines]
    bad = Gate()
    assert_event(bad, bad_timing, 8 + 1/6, "mission starting, duration: 1", 1, "mutated launch")
    assert len(bad.failures) == 1
    # A wrong typed booking cannot satisfy the distinct P-AUXALT evidence gate.
    typed = [line for line in lines if "<P-ALT at <BASE-01,0>> allocated to maintenance task: 1" in line]
    assert len(typed) == 2
    changed = typed.copy()
    changed[0] = changed[0].replace("<P-ALT at", "<P-CREW at")
    assert sum("<P-ALT at <BASE-01,0>> allocated to maintenance task: 1" in line for line in changed) == 1
    # Full report ledger comparison rejects an unlisted numeric mutation.
    report = parse(PARENT_RUN / "report-raw.json")
    system = next(t for t in report["report"]["tables"] if t["name"] == "SystemResults")
    row = expected_system({"SystemResults": system}, "factor1")[15]
    mutant = row.copy(); mutant[4] = 0.25
    assert not near(mutant[4], row[4])
    print("GO_STATIC: source seal, exact pair diff, 20 tables, timing, typed booking, report mutation")


if __name__ == "__main__":
    main()
