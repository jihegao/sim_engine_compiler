"""Read-only synthetic probes against the rejected author event gate."""
import json
import importlib.util
from pathlib import Path
import sys

PACKAGE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(PACKAGE))
old_path = Path(__file__).with_name("event_ledger.py")
spec = importlib.util.spec_from_file_location("rejected_event_ledger_v1", old_path)
assert spec and spec.loader
old = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = old
spec.loader.exec_module(old)
child_timeline, parse_log = old.child_timeline, old.parse_log
fixture_path = Path(__file__).with_name("self_check.py")
fixture_spec = importlib.util.spec_from_file_location("rejected_self_check_v1", fixture_path)
assert fixture_spec and fixture_spec.loader
fixture_module = importlib.util.module_from_spec(fixture_spec)
sys.modules[fixture_spec.name] = fixture_module
fixture_spec.loader.exec_module(fixture_module)
fixture_log = fixture_module.fixture_log

base = fixture_log()
mutations = {
    "orphan_return_continuation": base.replace(
        "Time: 36 resource shift 0 ended",
        "Time: 35  subtask 0 seqno 1 check return remote resources\n"
        "Time: 36 resource shift 0 ended",
        1,
    ),
    "false_free_snapshot": base.replace(
        "Time: 7.5 <P-CREW at <BASE-01,0>> allocated to maintenance task: 1  available now: 0\n",
        "Time: 7.5 <P-CREW at <BASE-01,0>> allocated to maintenance task: 1  available now: 0\n"
        "  Free resources at: <BASE-01,0> P-CREW 2\n",
        1,
    ),
    "extra_ready_increase": base.replace(
        "Time: 7.5 <TEACH-AIR-01,0> preparation started, mission: <BASIC-MISSION,TEACH-UNIT,0,0,0>\n",
        "Time: 7.5 <TEACH-AIR-01,0> preparation started, mission: <BASIC-MISSION,TEACH-UNIT,0,0,0>\n"
        "Time: 7.5 <TEACH-AIR-01,0> nbr ready increased at unit: <TEACH-UNIT at <BASE-01,0>>\n",
        1,
    ),
}
results = {}
for name, text in mutations.items():
    try:
        child_timeline(parse_log(text))
        results[name] = "ESCAPED_REJECTED_V1"
    except (AssertionError, ValueError, KeyError, TypeError) as exc:
        results[name] = f"rejected:{type(exc).__name__}:{str(exc)[:180]}"
print(json.dumps(results, sort_keys=True))
