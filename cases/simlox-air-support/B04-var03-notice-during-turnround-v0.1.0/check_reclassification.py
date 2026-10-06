"""Read-only author gate for the accepted B04.var03 early-notice observation."""

import hashlib
import importlib.util
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
SOURCE = ROOT / "B04-var05-turnround-breakdown-v0.1.0"
RUN = SOURCE / "runs" / "b04-var05-turnbreak-v010-ssh-20261006-01"
SOURCE_INPUT_SHA = "965a3acc431696e56b760b07323e4cf11cb571e030885fff708787ce84f3e42f"
SOURCE_CLOSURE_SHA = "58a4838596f96e07d5d20fff3cc4e02a7d3ef07f539d61f3a5c5caf0ca84b545"
SOURCE_REPORT_SHA = "df1c6055ce7cd32dea0e02112ab752bc34ec2484311e7d0baa44b04910a1c87a"
SOURCE_REPLAY_SHA = "70204f55e929ded374b3671b301708b34df488584050cf7c200c88cffa34c4af"
SOURCE_VERDICT_SHA = "fe9deac260919c28a7b5ee410f22d798d7d562de5b764d35b28d208bd0947fff"
CONTRACT_SHA = "cdae7dc60ab3593e48514811f9e4635bcc00f26f11039f3a189eeb4d1479e798"
REVIEW_SHA = "990eb30ddb127de1e3409dec04255451ba452c0b6782b68b8ff92b6bd639161a"
TIME = re.compile(r"^Time: ([0-9.]+) (.*)$", re.M)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, message, errors):
    if not condition:
        errors.append(message)


def timed(log, marker):
    return [(float(m.group(1)), m.group(2).strip(), m.start())
            for m in TIME.finditer(log) if marker in m.group(2)]


def one(log, marker, time, errors):
    found = timed(log, marker)
    require(len(found) == 1, f"event count {marker}", errors)
    if len(found) == 1:
        require(abs(found[0][0] - time) <= 0.00011, f"event time {marker}", errors)
    return found[0] if len(found) == 1 else None


def one_at(log, marker, time, errors):
    found = [event for event in timed(log, marker) if abs(event[0] - time) <= 0.00011]
    require(len(found) == 1, f"event at time {time}: {marker}", errors)
    return found[0] if len(found) == 1 else None


def exact_one(log, body, time, errors):
    found = [(float(m.group(1)), m.group(2).strip(), m.start())
             for m in TIME.finditer(log) if m.group(2).strip() == body]
    require(len(found) == 1, f"exact event count {body}", errors)
    if len(found) == 1:
        require(abs(found[0][0] - time) <= 0.00011, f"exact event time {body}", errors)
    return found[0] if len(found) == 1 else None


def validate():
    errors = []
    for path, expected, label in (
        (SOURCE / "native-input.json", SOURCE_INPUT_SHA, "source input"),
        (RUN / "closure.json", SOURCE_CLOSURE_SHA, "source closure"),
        (RUN / "report-raw.json", SOURCE_REPORT_SHA, "source raw report"),
        (SOURCE / "review" / "independent_replay.py", SOURCE_REPLAY_SHA, "source replay"),
        (SOURCE / "review" / "independent-verdict.json", SOURCE_VERDICT_SHA, "source verdict"),
        (HERE / "contract.json", CONTRACT_SHA, "new contract"),
        (HERE / "review" / "independent-contract-go-2026-10-07.md", REVIEW_SHA, "contract review"),
    ):
        require(path.is_file() and sha(path) == expected, f"{label} bytes differ", errors)
    if errors:
        return errors, 0
    closure = json.loads((RUN / "closure.json").read_text(encoding="utf-8-sig"))
    require(closure.get("run_id") == RUN.name and closure.get("error") is None,
            "source run identity/error differs", errors)
    raw = closure.get("raw", {})
    require(len(raw) == 13, "source raw count differs", errors)
    for name, pin in raw.items():
        path = RUN / name
        require(path.is_file() and path.stat().st_size == pin["bytes"] and sha(path) == pin["sha256"],
                f"source raw seal differs: {name}", errors)
    source = json.loads((SOURCE / "native-input.json").read_text(encoding="utf-8-sig"))
    tables = {table["name"]: table for table in source["model"]["tables"]}
    turn = tables["MissionTurnround"]["instances"][0]["rows"]
    profile = tables["OperationProfile"]["instances"][0]["rows"]
    subtasks = tables["TaskBreakDown"]["instances"][0]["rows"]
    require(turn == [["BASIC-MISSION", "TEACH-AIR-01", "BASE-01", 1.0, "TURN-STEPS", None, None]],
            "turnround source differs", errors)
    require(len(profile) == 2 and profile[1][0:5] == ["BASIC-SCHEDULE", "BASIC-MISSION", 24.75, "SCHEDULED", 1],
            "second mission source differs", errors)
    require([row[0:4] for row in subtasks[-2:]] ==
            [["TURN-STEPS", 1, "INSPECT", 1 / 6], ["TURN-STEPS", 2, "SERVICE", 1 / 3]],
            "turnround subtask source differs", errors)
    log = (RUN / "model.log").read_text(encoding="utf-8-sig", errors="replace")
    m0 = "<BASIC-MISSION,TEACH-UNIT,0,0,0>"
    m1 = "<BASIC-MISSION,TEACH-UNIT,0,0,1>"
    aircraft = "<TEACH-AIR-01,0>"
    events = [
        one(log, m0 + " mission starting, duration: 2 : " + aircraft, 21.5, errors),
        one(log, m0 + " mission success:", 23.5, errors),
        one(log, m0 + " mission completed: " + aircraft, 23.5, errors),
        one(log, aircraft + " turnround started, mission: " + m0, 23.5, errors),
        one(log, "subtask 2 seqno 1 within system turnround task 1 on " + aircraft + " started", 23.5, errors),
        one(log, "subtask 3 seqno 2 within system turnround task 1 on " + aircraft + " started", 23.6667, errors),
        one_at(log, "mission ordered: BASIC-MISSION", 23.75, errors),
        one(log, m1 + " mission created:", 23.75, errors),
        one(log, m1 + " mission activated", 23.75, errors),
        one(log, m1 + " mission preassigns a system: " + aircraft, 23.75, errors),
        exact_one(log, "system turnround task 1 on " + aircraft + " completed", 24.0, errors),
        one(log, aircraft + " turnround ended, mission: " + m0, 24.0, errors),
        one_at(log, "System arrives " + aircraft + ", mission success", 24.0, errors),
        one(log, m1 + " mission allocates system: " + aircraft, 24.0, errors),
        one(log, aircraft + " preparation started, mission: " + m1, 24.0, errors),
        one(log, aircraft + " preparation ended, mission: " + m1, 24.5, errors),
        one(log, m1 + " mission starting, duration: 2 : " + aircraft, 24.75, errors),
        one(log, m1 + " mission success:", 26.75, errors),
        one(log, m1 + " mission completed: " + aircraft, 26.75, errors),
    ]
    if all(events):
        positions = [event[2] for event in events]
        require(positions == sorted(positions), "physical event order differs", errors)
        require(events[3][0] < events[6][0] < events[10][0] <= events[13][0] < events[16][0],
                "notice/turnround/allocation/launch order differs", errors)
    require(not timed(log, m1 + " mission cancelled") and not timed(log, m1 + " mission aborted"),
            "second mission cancelled or aborted", errors)
    # Re-run the already accepted independent full-ledger verifier as a pure function.
    replay_file = SOURCE / "review" / "independent_replay.py"
    spec = importlib.util.spec_from_file_location("accepted_b04_var05_replay", replay_file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    full = module.replay()
    require(full.get("decision") == "GO_BOUNDED" and full.get("checks") == 4595 and
            not full.get("failures") and full.get("report_cells_checked") == 4044,
            "accepted full-ledger replay differs", errors)
    return errors, full.get("report_cells_checked", 0)


def main():
    try:
        errors, report_cells = validate()
    except Exception as exc:
        errors, report_cells = [f"checker exception: {type(exc).__name__}: {exc}"], 0
    result = {"schema": "simlox-b04-var03-read-only-author/v1",
              "decision": "GO_BOUNDED" if not errors else "NO_GO",
              "passed": not errors, "problems": errors,
              "accepted_run_id": RUN.name, "accepted_closure_sha256": SOURCE_CLOSURE_SHA,
              "report_cells_replayed": report_cells,
              "scope": "read-only classification of next mission notice during an accepted linked turnround"}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
