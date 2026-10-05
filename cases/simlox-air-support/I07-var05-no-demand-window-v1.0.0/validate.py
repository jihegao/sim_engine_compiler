"""Read-only author mapping of accepted I07.var02 to a no-depot-demand interval."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "I07-var02-rosiz-v1.0.1"
RUN = PARENT / "runs/i07-var02-rosiz-v101-ssh-20261005-01"
FAIL: list[str] = []
COUNT = 0


def check(ok: bool, label: str) -> None:
    global COUNT
    COUNT += 1
    if not ok:
        FAIL.append(label)


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def model_tables(doc: dict) -> dict:
    return {t["name"]: t for t in doc["model"]["tables"]}


def rows(doc: dict, name: str) -> list[dict]:
    t = next(t for t in doc["report"]["tables"] if t["name"] == name)
    cols = [c["name"] for c in t["columns"]]
    return [dict(zip(cols, row)) for inst in t["instances"] for row in inst["rows"]]


contract = load(HERE / "contract.json")
parent = contract["accepted_parent"]
index = load(PARENT / "evidence-index.json")
closure = load(RUN / "closure.json")
outcome = load(RUN / "outcome.json")
check((contract["case_id"], contract["variant_id"], contract["version"]) ==
      ("I07", "I07.var05", "1.0.0-candidate"), "contract identity")
check(parent["run_id"] == index["run"]["run_id"] == closure["run_id"] == RUN.name,
      "accepted run identity")
for name, path in (("evidence_index_sha256", PARENT / "evidence-index.json"),
                   ("contract_sha256", PARENT / "contract.json"),
                   ("signoff_sha256", PARENT / "cli-scope-signoff-2026-10-05.md"),
                   ("run_closure_sha256", RUN / "closure.json"),
                   ("control_input_sha256", PARENT / "control-input.json"),
                   ("change_input_sha256", PARENT / "change-input.json"),
                   ("independent_review_sha256", PARENT / "review/independent-readonly-2026-10-05.json")):
    check(path.is_file() and sha(path) == parent[name], f"parent {name} pin")
check(sha(Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf")) ==
      contract["manual_pdf_sha256"], "installed manual pin")
check(len(index["source"]) == 15 and len(index["run"]["raw"]) == 22,
      "accepted source/raw inventory")
for name, seal in index["source"].items():
    path = PARENT / name
    check(path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"],
          f"published parent source {name}")
check(sha(RUN / "invocation.json") == index["run"]["invocation"]["sha256"] ==
      closure["invocation_sha256"], "invocation pin")
check(sha(RUN / "closure.json") == index["run"]["closure"]["sha256"], "closure index pin")
check(closure["source_hashes_before"] == closure["source_hashes_after"] and closure["error"] is None,
      "accepted source stability")
for name, seal in index["run"]["raw"].items():
    path = RUN / name
    check(path.is_file() and path.stat().st_size == seal["bytes"] and sha(path) == seal["sha256"]
          and closure["raw"][name] == seal, f"accepted raw {name}")
check(outcome["arms"] == {"control": "completed", "change": "completed"} and
      all(outcome["converter_summaries"][a] == [0, 1, 0] and
          outcome["warning_codes"][a] == ["108"] for a in ("control", "change")),
      "accepted native conversion")
independent = load(PARENT / "review/independent-readonly-2026-10-05.json")
check(independent["decision"] == "GO_BOUNDED" and independent["passed"] is True and
      independent["checks_passed"] == independent["checks_total"] == 3476 and
      independent["closure_sha256"] == sha(RUN / "closure.json"), "accepted independent verdict")

control = load(PARENT / "control-input.json")
change = load(PARENT / "change-input.json")
ct, cht = model_tables(control), model_tables(change)
check({key for key in ct if ct[key] != cht[key]} == {"ChangesStockAllocation"}, "sole paired delta")
check(ct["ChangesStockAllocation"]["instances"][0]["rows"] == [[None] * 6] and
      cht["ChangesStockAllocation"]["instances"][0]["rows"] ==
      [["AIR_BASIC", "TEACH-DU-01", "DEPOT-01", 5.0, 1, None]], "h5 change source")
check(ct["StockAllocation"]["instances"][0]["rows"][1][3:7] == [4, 2, None, None],
      "nominal four default opening four initial ROSIZ two")

for arm in ("control", "change"):
    log = (RUN / f"{arm}.log").read_text(encoding="utf-8-sig", errors="replace")
    events = []
    for line in log.splitlines():
        match = re.match(r"^Time: ([0-9.]+) (.*)$", line)
        if match and 5 <= float(match.group(1)) < 10:
            events.append((float(match.group(1)), match.group(2)))
    check(len(events) > 0 and any(t == 7 for t, _ in events), f"{arm} interval contains mission events")
    check(not any("<TEACH-DU-01,0,DEPOT-01,0>" in event or
                  "item transfer task" in event or "reorder task" in event or
                  "Delivery with" in event for _, event in events),
          f"{arm} no depot item demand/transfer/order/delivery [5,10)")
    check("Time: 10 <TEACH-DU-01,0,DEPOT-01,0> Item demand arrives" in log and
          "Time: 10 <TEACH-DU-01,0,DEPOT-01,0> Take replacement item <TEACH-DU-01,0,0> from stock" in log,
          f"{arm} first depot stock action h10")
    stock = re.findall(r"^  Stock at: <TEACH-DU-01,0,DEPOT-01,0> Level: (\d+) Items:(.*)$",
                       log, re.M)
    check(stock[0] == ("4", "<TEACH-DU-01,0,0>,<TEACH-DU-01,0,1>,<TEACH-DU-01,0,2>,<TEACH-DU-01,0,3>,")
          and stock[1][0] == "3", f"{arm} no intermediate depot stock snapshot")
    report = load(RUN / f"{arm}-report-raw.json")
    item = rows(report, "ItemResults")
    check(len(item) == 72, f"{arm} accepted 72 selected bins")
    for i in range(9, 21):
        row = item[i]
        check((row["IID"], row["STID"], row["STINT"], row["ETINT"]) ==
              ("TEACH-DU-01", "DEPOT-01", i / 2, (i + 1) / 2), f"{arm} boundary bin {i}")
        if i < 20:
            check((row["STSZ"], row["STOHA"], row["NRO"], row["NBO"]) ==
                  (4, 4, 0, 0), f"{arm} unchanged depot bin {i}")
    check((item[20]["STOHA"], item[20]["NRO"]) ==
          ((3, 0) if arm == "control" else (3, 1)), f"{arm} h10 demand/order boundary")

result = {"schema": "simlox-i07-var05-author-source-replay/v1",
          "parent_run_id": RUN.name, "parent_closure_sha256": sha(RUN / "closure.json"),
          "passed": not FAIL, "checks": COUNT, "checks_passed": COUNT - len(FAIL), "failures": FAIL,
          "observed": "No depot item-stock demand, transfer, order, delivery or stock move in [5,10); ten half-hour bins per arm retain STSZ4/STOHA4/NRO0/NBO0. First depot demand h10.",
          "limits": contract["limits"]}
destination = HERE / "review/author-validation-2026-10-05.json"
destination.parent.mkdir(exist_ok=True)
destination.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
print(f"{'GO' if result['passed'] else 'NO-GO'} {result['checks_passed']}/{COUNT}")
for failure in FAIL:
    print(failure)
raise SystemExit(0 if result["passed"] else 1)
