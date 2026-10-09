"""In-memory private negatives for exact I05.var07 source and event boundaries."""
from __future__ import annotations

import copy
import json

from check_roundtrip import PARENT_INPUT, PARENT_INPUT_PIN, PARENT_EXPORT, PARENT_EXPORT_PIN, predicted, source_oracles
from event_ledger import semantic
from model_common import HERE, LOG_PIN, REPORT_PIN, compare_tables, exact, strict_json, typed_equal

def reject(action, label: str) -> None:
    try: action()
    except (AssertionError,ValueError,TypeError,KeyError,IndexError,UnicodeError): return
    raise AssertionError(("private mutant accepted",label))

def run() -> dict[str,object]:
    parent_input=strict_json(exact(PARENT_INPUT,PARENT_INPUT_PIN))
    parent_export=strict_json(exact(PARENT_EXPORT,PARENT_EXPORT_PIN))
    oracle=source_oracles()
    assert typed_equal(predicted(parent_input,"authored"),oracle["authored"])
    assert typed_equal(predicted(parent_export,"exported"),oracle["exported"])
    parent_log_path=PARENT_INPUT.parent/"runs/b04-v101-turnround-20260930-01/model.log"
    parent_log=exact(parent_log_path,{"bytes":9088,"sha256":"ea2cd9cd124b499f69674a9bb8a70d44ec2ab9ffa0fa8b602f34b45f9e37163e"})
    parent_lines=parent_log.decode("utf-8").splitlines()
    assert len(parent_lines)==115 and "planned to last for 1 hours" in parent_lines[46]
    assert "planned to last for 1 hours" in parent_lines[101]
    child_log=exact(HERE/"preserved-design/expected-model.log",LOG_PIN)
    assert semantic(child_log)["timed_lines"]==107
    expected_report=strict_json(exact(HERE/"preserved-design/expected-report.json",REPORT_PIN))
    assert typed_equal(expected_report,copy.deepcopy(expected_report))
    rejected=0
    def bad(action,label):
        nonlocal rejected
        reject(action,label); rejected+=1
    bad(lambda:predicted(parent_input,"exported"),"source wrong arm")
    bad(lambda:predicted(parent_export,"authored"),"export wrong arm")
    bad(lambda:predicted(parent_input,"unknown"),"unknown arm")
    bad(lambda:strict_json(b'{"a":1,"a":2}'),"duplicate JSON")
    bad(lambda:strict_json(b'{"a":NaN}'),"nonfinite JSON")
    bad(lambda:strict_json(b'\xef\xbb\xbf{"a":1}'),"model BOM")
    def edit_model(arm, action):
        clone=copy.deepcopy(oracle[arm]); tables=clone["model"]["tables"]
        action(tables)
        assert compare_tables(oracle[arm]["model"]["tables"],tables)==(211 if arm=="authored" else 374)
        assert typed_equal(oracle[arm],clone)
    bad(lambda:edit_model("authored",lambda t:t.insert(12,t.pop(32))),"authored wrong insertion")
    bad(lambda:edit_model("exported",lambda t:t.insert(12,t.pop(32))),"export wrong insertion")
    bad(lambda:edit_model("exported",lambda t:t.insert(31,t.pop(32))),"export adjacent insertion")
    bad(lambda:edit_model("exported",lambda t:t.insert(4,t.pop(3))),"unrelated table reorder")
    bad(lambda:edit_model("exported",lambda t:t.append(copy.deepcopy(t[32]))),"duplicate change table")
    bad(lambda:edit_model("exported",lambda t:t.pop(32)),"missing change table")
    bad(lambda:edit_model("authored",lambda t:t[32]["instances"][0]["rows"][0].__setitem__(4,True)),"duration bool")
    bad(lambda:edit_model("exported",lambda t:t[32]["instances"][0]["rows"][0].__setitem__(3,25.0)),"export integral double typed")
    bad(lambda:edit_model("exported",lambda t:t[32]["columns"][0].__setitem__("key",1)),"key bool alias")
    bad(lambda:edit_model("exported",lambda t:t[32]["columns"][3].pop("key")),"missing TIMEC key")
    bad(lambda:edit_model("authored",lambda t:t[32]["instances"][0].__setitem__("rows",{})),"rows container")
    bad(lambda:semantic(child_log.replace(b"1.5 hours",b"1 hours",1)),"child wrong duration")
    bad(lambda:semantic(child_log.replace(b"28.5",b"28",1)),"child wrong ready time")
    bad(lambda:semantic(child_log[:-2]),"log terminal CRLF")
    def report_edit(action):
        clone=copy.deepcopy(expected_report); action(clone["report"]["tables"])
        assert compare_tables(expected_report["report"]["tables"],clone["report"]["tables"])==4044
        assert typed_equal(expected_report,clone)
    bad(lambda:report_edit(lambda t:t[2]["instances"][0]["rows"][56].__setitem__(4,1)),"report wrong numeric cell")
    bad(lambda:report_edit(lambda t:t[2]["instances"][0]["rows"][56].__setitem__(4,0.0)),"report int-to-float type")
    bad(lambda:report_edit(lambda t:t[2]["columns"][0].__setitem__("key",1)),"report key bool alias")
    return {"schema":"i05-var07-private-negative-check/v101","passed":True,
            "authored_positive_cells":211,"exported_positive_cells":374,
            "frozen_physical_lines":115,"frozen_report_cells":4044,
            "rejected_private_mutants":rejected,"native_calls":0,"accepted_checker_calls":0}

if __name__=="__main__": print(json.dumps(run(),sort_keys=True))
