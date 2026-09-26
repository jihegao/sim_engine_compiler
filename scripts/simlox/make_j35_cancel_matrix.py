"""Build isolated two-SID SIMLOX cancellation-rule probes from verified phase6 A."""

from __future__ import annotations

import copy
import argparse
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SOURCE = Path("C:/Users/user/Documents/Codex/2026-09-26/simlox-j35-event-parity/workspace/evidence/phase6/a-pri-a-v4/a-pri-a-v4.json")
SOURCE_SHA = "ec93b454aceb58a6fb49f47fe1e16064ffb21a9e699c785fea39276c7e4c6b17"
OUTPUT = REPO / "data/local/j35-contract-probes"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def table(model: dict, name: str) -> dict:
    return next(t for t in model["model"]["tables"] if t["name"] == name)


def rows(t: dict) -> list[dict]:
    cols = [c["name"] for c in t["columns"]]
    return [dict(zip(cols, row)) for instance in t["instances"] for row in instance["rows"]]


def set_field(t: dict, field: str, value: object, selector=lambda row: True) -> None:
    cols = [c["name"] for c in t["columns"]]
    idx = cols.index(field)
    for instance in t["instances"]:
        for row in instance["rows"]:
            if selector(dict(zip(cols, row))):
                row[idx] = value


def field_diff(before: dict, after: dict) -> dict:
    result = {}
    a = {t["name"]: rows(t) for t in before["model"]["tables"]}
    b = {t["name"]: rows(t) for t in after["model"]["tables"]}
    for name in sorted(a.keys() | b.keys()):
        if a.get(name) == b.get(name):
            continue
        changes = []
        for i in range(max(len(a.get(name, [])), len(b.get(name, [])))):
            old = a.get(name, [])[i] if i < len(a.get(name, [])) else {}
            new = b.get(name, [])[i] if i < len(b.get(name, [])) else {}
            for key in sorted(old.keys() | new.keys()):
                if old.get(key) != new.get(key):
                    changes.append({"row_index": i, "field": key, "before": old.get(key), "after": new.get(key)})
        result[name] = changes
    return result


def make(stem: str, *, pmt: float, dtim: float = 20 / 60, stim: float = 56, personnel: int = 40,
         equipment: int = 60, prep: bool = True, next_wave: bool = False,
         step_shorten: int = 0, pm_step_duration: float | None = None) -> None:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    model = copy.deepcopy(source)
    mission = table(model, "MissionType")
    for field, value in {"NOS": 2, "MNOS": 2, "NOPER": 3, "DURN": 1}.items():
        set_field(mission, field, value)
    preparation = table(model, "MissionPreparation")
    duration = (142 - step_shorten) / 60 if prep else 0
    set_field(preparation, "DURN", duration)
    set_field(preparation, "TID", "MISSION_PREP" if prep else None)
    set_field(table(model, "PMLocation"), "PMT", pmt)
    if pm_step_duration is not None:
        set_field(table(model, "TaskBreakDown"), "DURN", pm_step_duration,
                  lambda r: r["TID"] == "PM_25H" and r["SEQ"] == 1)
    set_field(table(model, "OperationProfile"), "DTIM", dtim)
    set_field(table(model, "OperationProfile"), "STIM", stim)
    if next_wave:
        t = table(model, "OperationProfile")
        second = copy.deepcopy(t["instances"][0]["rows"][0])
        cols = [c["name"] for c in t["columns"]]
        second[cols.index("STIM")] = 57
        second[cols.index("NOTE")] = "adjacent wave after first cancellation"
        t["instances"][0]["rows"].append(second)
    resource = table(model, "ResourceAllocation")
    set_field(resource, "RQTY", personnel, lambda r: r["RID"] == "PERSONNEL")
    set_field(resource, "RQTY", equipment, lambda r: r["RID"] == "DEVICE")
    if step_shorten:
        # Change one real preparation step and the corresponding total duration.
        # Step 8 is 23 minutes in this inherited activity.
        t = table(model, "TaskBreakDown")
        set_field(t, "DURN", (23 - step_shorten) / 60,
                  lambda r: r["TID"] == "MISSION_PREP" and r["SEQ"] == 8)
    assert len([r for r in rows(table(model, "MissionSystem")) if r["MTID"] == "BM-J35-43D"]) == 2
    assert all(r["FRT"] == 0 for r in rows(table(model, "Item")))
    assert all(r["QTYPS"] == 1 for r in rows(table(model, "SystemDeployment")))
    dest = OUTPUT / stem
    dest.mkdir(parents=True, exist_ok=True)
    path = dest / f"{stem}.json"
    if path.exists():
        raise FileExistsError(path)
    path.write_text(json.dumps(model, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    provenance = {
        "source": str(SOURCE), "source_sha256": SOURCE_SHA,
        "input": str(path), "input_sha256": sha256(path),
        "changes_from_source": field_diff(source, model),
        "probe_parameters": {"pm_location_pmt_hours": pmt, "pm_step_duration_hours": pm_step_duration,
                             "dtim_hours": dtim, "stim_hours": stim,
                             "prep_minutes": 142 - step_shorten if prep else 0,
                             "personnel_capacity": personnel, "equipment_capacity": equipment,
                             "next_wave": next_wave},
        "scope": "two stable SIDs, zero failure, cancellation mechanism only; not full J35",
    }
    (dest / "provenance.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(stem, provenance["input_sha256"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stem", help="Generate one named case; use a fresh data/local directory for all cases")
    args = parser.parse_args()
    assert sha256(SOURCE) == SOURCE_SHA
    cutoff = 56 + 20 / 60 - 142 / 60
    assert abs(cutoff - (24 + (30 - 2 / 60))) < 1e-12
    for stem, options in [
        ("p1-all-ready", dict(pmt=24)),
        ("p1-before", dict(pmt=29.95)),
        ("p1-tie", dict(pmt=30 - 2 / 60)),
        ("p1-after", dict(pmt=29.983333333333334)),
        ("p1-resource-one", dict(pmt=29.95, personnel=1, equipment=1)),
        ("p1-zero-before", dict(pmt=32.31666666666667, prep=False)),
        ("p1-zero-after", dict(pmt=32.35, prep=False)),
        ("p1-dtim40", dict(pmt=30.2, dtim=40 / 60)),
        ("p1-step-short", dict(pmt=30, step_shorten=20)),
        ("p1-next-wave", dict(pmt=29.983333333333334, next_wave=True)),
        ("p1-stim-earlier", dict(pmt=29.95, stim=55.5)),
        ("p1-stim-later", dict(pmt=29.95, stim=56.5)),
        # V1 PMLocation.PMT did not move the observed PM completion from 48h.
        # V2 changes the actual PM TaskBreakDown step from its 24h source.
        ("p1v2-pm-before", dict(pmt=24, pm_step_duration=29.95)),
        ("p1v2-pm-tie", dict(pmt=24, pm_step_duration=30 - 2 / 60)),
        ("p1v2-pm-after", dict(pmt=24, pm_step_duration=29.983333333333334)),
        ("p1v2-pm-dtim40-before", dict(pmt=24, pm_step_duration=30.2, dtim=40 / 60)),
        ("p1v2-pm-dtim40-after", dict(pmt=24, pm_step_duration=30.4, dtim=40 / 60)),
        ("p1v2-pm-step-short", dict(pmt=24, pm_step_duration=30.2, step_shorten=20)),
        ("p1v2-zero-before", dict(pmt=24, pm_step_duration=32.31666666666667, prep=False)),
        ("p1v2-zero-after", dict(pmt=24, pm_step_duration=32.35, prep=False)),
    ]:
        if args.stem is None or args.stem == stem:
            make(stem, **options)


if __name__ == "__main__":
    main()
