"""Private in-memory negative checks for the package adapters; no SIMLOX call."""
from __future__ import annotations

import copy
import json
from pathlib import Path

from check_roundtrip import (PARENT_EXPORT, PARENT_EXPORT_PIN, PARENT_INPUT,
                             PARENT_INPUT_PIN, NEW_TABLE, predicted_child)
from event_ledger import oracle, semantic
from model_common import HERE, PATTERN_PIN, REPORT_RULES_PIN, compare_tables, exact, strict_json, typed_equal
from report_oracle import compare
from source_gate import ACCEPTED_PROOFS, accepted_powershell_receipt_bytes

def reject(action, label: str) -> None:
    try:
        action()
    except (AssertionError, ValueError, TypeError, KeyError, IndexError, UnicodeError):
        return
    raise AssertionError(("private mutant accepted", label))

def run() -> dict[str, object]:
    parent_input = strict_json(exact(PARENT_INPUT, PARENT_INPUT_PIN))
    parent_export = strict_json(exact(PARENT_EXPORT, PARENT_EXPORT_PIN))
    authored = predicted_child(parent_input, "authored")
    exported = predicted_child(parent_export, "exported")
    assert compare_tables(authored["model"]["tables"], strict_json((HERE / "native-input.json").read_bytes())["model"]["tables"]) == 284
    assert compare_tables(exported["model"]["tables"], copy.deepcopy(exported)["model"]["tables"]) == 379
    rejected = 0
    def bad(action, label):
        nonlocal rejected
        reject(action, label)
        rejected += 1
    bad(lambda: predicted_child(parent_input, "exported"), "authored wrong arm")
    bad(lambda: predicted_child(parent_export, "authored"), "export wrong arm")
    bad(lambda: predicted_child(parent_input, "unknown"), "unknown prediction arm")
    bad(lambda: strict_json(b'{"a":1,"a":2}'), "duplicate JSON member")
    bad(lambda: strict_json(b'{"a":NaN}'), "nonfinite JSON")
    bad(lambda: strict_json(b'\xef\xbb\xbf{"a":1}'), "BOM JSON")
    bom = b"\xef\xbb\xbf"
    for path, size, sha in ACCEPTED_PROOFS[1:]:
        raw = exact(path, {"bytes":size,"sha256":sha})
        assert raw.startswith(bom)
        assert type(accepted_powershell_receipt_bytes(raw)) is dict
        bad(lambda raw=raw: accepted_powershell_receipt_bytes(raw[3:]), "accepted receipt missing BOM")
        bad(lambda raw=raw: accepted_powershell_receipt_bytes(bom + raw), "accepted receipt double BOM")
    bad(lambda: accepted_powershell_receipt_bytes(bom+b'{"a":1,"a":2}'), "accepted receipt duplicate JSON key")
    bad(lambda: accepted_powershell_receipt_bytes(bom+b'{"a":NaN}'), "accepted receipt nonfinite JSON")
    def changed_model(table_edit):
        clone = copy.deepcopy(authored)
        table_edit(clone["model"]["tables"][12])
        return compare_tables(authored["model"]["tables"], clone["model"]["tables"])
    bad(lambda: changed_model(lambda t: t["instances"][0]["rows"][0].__setitem__(3, True)), "DIRPT bool")
    bad(lambda: changed_model(lambda t: t["instances"][0]["rows"][0].__setitem__(3, 1.0)), "DIRPT value")
    bad(lambda: changed_model(lambda t: t["columns"][0].__setitem__("key", 1)), "column key bool alias")
    bad(lambda: changed_model(lambda t: t["columns"][2].pop("key")), "missing TIMEC key")
    bad(lambda: changed_model(lambda t: t["columns"][3].__setitem__("key", False)), "extra DIRPT key")
    bad(lambda: changed_model(lambda t: t["instances"][0].__setitem__("rows", {"bad":1})), "rows container")
    bad(lambda: changed_model(lambda t: t["instances"][0]["rows"].__setitem__(0, {"bad":1})), "row container")
    bad(lambda: changed_model(lambda t: t["instances"][0]["rows"].append(copy.deepcopy(NEW_TABLE["instances"][0]["rows"][0]))), "extra row")
    def changed_export(table_edit):
        clone = copy.deepcopy(exported)
        table_edit(clone["model"]["tables"])
        return compare_tables(exported["model"]["tables"], clone["model"]["tables"])
    def move(tables, source, target):
        tables.insert(target, tables.pop(source))
    bad(lambda: changed_export(lambda t: move(t, 17, 12)), "export index12, old failed expectation")
    bad(lambda: changed_export(lambda t: move(t, 17, 18)), "export adjacent wrong index")
    bad(lambda: changed_export(lambda t: move(t, 3, 4)), "export unrelated reorder")
    bad(lambda: changed_export(lambda t: t.append(copy.deepcopy(NEW_TABLE))), "export duplicate change table")
    bad(lambda: changed_export(lambda t: t.pop(17)), "export missing change table")
    bad(lambda: changed_export(lambda t: t[17]["columns"][0].__setitem__("key", 1)), "export key bool alias")
    bad(lambda: changed_export(lambda t: t[17]["instances"][0]["rows"][0].__setitem__(3, 1.0)), "export DIRPT wrong cell")
    def wrong_authored_order():
        clone = copy.deepcopy(authored)
        move(clone["model"]["tables"], 12, 17)
        return compare_tables(authored["model"]["tables"], clone["model"]["tables"])
    bad(wrong_authored_order, "authored table moved to export index")
    patterns = strict_json(exact(HERE / "preserved-oracle/log-patterns.json", PATTERN_PIN))
    predicates = strict_json(exact(HERE / "preserved-oracle/report-predicates.json", REPORT_RULES_PIN))
    assert patterns["physical_lines"] == 222 and patterns["timed_lines"] == 186
    assert predicates["cell_count"] == 4044
    assert len(patterns["lines"]) == 222 and len(predicates["predicates"]) == 4044
    # The prospective v101 PURE receipt separately attests parent and synthetic-child
    # positives, all cells, and 18 below-hash mutations. This adapter tests its own
    # table/typed boundary here and keeps the v101 methods byte-frozen.
    return {"schema":"i05-var04-private-negative-check/v103","passed":True,
            "authored_positive_cells":284,"exported_positive_cells":379,
            "frozen_physical_line_patterns":222,"frozen_report_predicates":4044,
            "rejected_private_mutants":rejected,"native_calls":0,"accepted_checker_calls":0}

if __name__ == "__main__":
    print(json.dumps(run(), sort_keys=True))
