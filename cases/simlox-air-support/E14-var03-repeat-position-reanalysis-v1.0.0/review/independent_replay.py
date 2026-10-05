"""Independent, read-only replay of the accepted E14 repeated-position evidence."""

from __future__ import annotations

import collections
import hashlib
import json
import pathlib
import re
import subprocess


HERE = pathlib.Path(__file__).resolve().parent
CASE = HERE.parent
ROOT = CASE.parents[2]
PARENT = CASE.parent / "E14-var01-02-extra-removal-v1.0.0"
E05 = CASE.parent / "E05-local-repair-reissue-v1.0.0"
CONTRACT = json.loads((CASE / "contract.json").read_bytes())
PINS = CONTRACT["accepted_parent"]
CHECKS = 0


def check(condition: bool, label: str) -> None:
    global CHECKS
    CHECKS += 1
    if not condition:
        raise AssertionError(label)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def git_blob(path: pathlib.Path) -> bytes:
    name = path.relative_to(ROOT).as_posix()
    return subprocess.check_output(
        ["git", "-C", str(ROOT), "show", f"{PINS['published_commit']}:{name}"]
    )


def sealed(path: pathlib.Path, record: dict, label: str) -> None:
    data = path.read_bytes()
    check(len(data) == record["bytes"] and digest(data) == record["sha256"], label)


def main() -> None:
    check(
        CONTRACT["case_id"] == "E14" and CONTRACT["variant_id"] == "E14.var03",
        "contract identity",
    )
    for path, expected in (
        (PARENT / "cli-scope-signoff-2026-10-05.md", PINS["signoff_git_sha256"]),
        (E05 / "cli-scope-signoff-2026-09-29.md", CONTRACT["prerequisite"]["signoff_git_sha256"]),
        (PARENT / "review" / "independent-verdict.json", PINS["independent_verdict_sha256"]),
    ):
        check(digest(git_blob(path)) == expected, f"published Git pin: {path.name}")

    local = (PARENT / "evidence-index.json").read_bytes()
    published = git_blob(PARENT / "evidence-index.json")
    check(
        (len(local), digest(local))
        == (PINS["evidence_index_local_bytes"], PINS["evidence_index_local_crlf_sha256"]),
        "historical local index byte pin",
    )
    check(
        (len(published), digest(published))
        == (PINS["evidence_index_published_git_bytes"], PINS["evidence_index_published_git_lf_sha256"]),
        "published Git index byte pin",
    )
    check(local.replace(b"\r\n", b"\n") == published, "index CRLF/LF byte relation")
    index = json.loads(local)

    # Verify all accepted authored source records against both the checkout and
    # their published Git blobs. These files are not generated or modified here.
    disk_bad: list[str] = []
    git_bad: list[str] = []
    for name, record in index["source"].items():
        path = PARENT / name
        disk = path.read_bytes()
        blob = git_blob(path)
        if len(disk) != record["bytes"] or digest(disk) != record["sha256"]:
            disk_bad.append(name)
        if len(blob) != record["bytes"] or digest(blob) != record["sha256"]:
            git_bad.append(name)
    check(len(index["source"]) == 23 and not disk_bad, f"parent source checkout pins: {disk_bad}")
    check(not git_bad, f"parent source Git pins: {git_bad}")

    runs: dict[str, pathlib.Path] = {}
    raw_count = 0
    for kind, run_id_key, closure_key in (
        ("native", "native_run_id", "native_closure_sha256"),
        ("selected_item_report", "selected_report_run_id", "selected_report_closure_sha256"),
    ):
        info = index["runs"][kind]
        check(info["run_id"] == PINS[run_id_key], f"{kind} run ID")
        directory = PARENT / "runs" / info["run_id"]
        closure = (directory / "closure.json").read_bytes()
        check(
            len(closure) == info["closure"]["bytes"]
            and digest(closure) == PINS[closure_key] == info["closure"]["sha256"],
            f"{kind} closure",
        )
        for name, record in info["raw"].items():
            sealed(directory / name, record, f"{kind} raw {name}")
            raw_count += 1
        runs[kind] = directory
    check(raw_count == 164, "164 accepted raw seals")

    extra_pattern = re.compile(
        r"^Time: ([0-9.]+) <TEACH-LRU-01,0,BASE-01,0> item SURP task "
        r"(\d+) on <TEACH-LRU-01,0,(\d+)> extra removal of subitem "
        r"<(TEACH-SRU-0[12]),0,(\d+)>"
    )
    counts: dict[str, int] = {}
    groups: list[dict] = []
    extras_total = 0
    for seed in range(2, 7):
        for arm in ("control", "extra"):
            lines = (runs["native"] / f"seed{seed}-{arm}.log").read_text(
                encoding="latin-1"
            ).splitlines()
            events: list[tuple[int, float, int, int, str, int]] = []
            for line_no, line in enumerate(lines):
                match = extra_pattern.search(line)
                if match:
                    events.append(
                        (
                            line_no,
                            float(match[1]),
                            int(match[2]),
                            int(match[3]),
                            match[4],
                            int(match[5]),
                        )
                    )
            counts[f"seed{seed}-{arm}"] = len(events)
            if arm == "control":
                check(not events, f"seed {seed} control has no extra removal")
                continue
            extras_total += len(events)
            by_position: dict[tuple[int, int, str], list[tuple[int, float, int, int]]] = (
                collections.defaultdict(list)
            )
            for i, (line_no, time, task, lru, iid, removed) in enumerate(events):
                end = events[i + 1][0] if i + 1 < len(events) else len(lines)
                segment = lines[line_no:end]
                demand_text = (
                    "Item demand arrives from pos <TEACH-LRU-01,0,BASE-01,0> "
                    f"item requiring maintenance is <{iid},0,{removed}>"
                )
                demands = [j for j, line in enumerate(segment) if demand_text in line]
                check(len(demands) == 1, f"seed {seed} demand for {iid}/{removed}")
                issues: list[int] = []
                for line in segment[demands[0] + 1 :]:
                    if "Item demand arrives" in line:
                        break
                    match = re.search(
                        r"Take replacement item <" + iid + r",0,(\d+)> from stock",
                        line,
                    )
                    if match:
                        issues.append(int(match[1]))
                check(len(issues) == 1, f"seed {seed} issue for {iid}/{removed}")
                by_position[(task, lru, iid)].append((line_no, time, removed, issues[0]))
            for (task, lru, iid), sequence in by_position.items():
                if len(sequence) < 2:
                    continue
                check(len({event[2] for event in sequence}) == len(sequence), "distinct removed IDs")
                check(len({event[3] for event in sequence}) == len(sequence), "distinct issued IDs")
                for previous, current in zip(sequence, sequence[1:]):
                    check(previous[1] < current[1], "strict serial timestamps")
                    between = lines[previous[0] + 1 : current[0]]
                    completion = re.compile(
                        r"fit subitem subtask \d+ seqno \d+ within item SURP task "
                        + str(task)
                        + r" on <TEACH-LRU-01,0,"
                        + str(lru)
                        + r"> completed"
                    )
                    check(
                        any(completion.search(line) for line in between),
                        "previous fit completes before next same-position extra removal",
                    )
                groups.append(
                    {
                        "seed": seed,
                        "task": task,
                        "lru_physical_id": lru,
                        "sru_iid": iid,
                        "events": [
                            {
                                "time": time,
                                "removed_physical_id": removed,
                                "issued_physical_id": issued,
                            }
                            for _, time, removed, issued in sequence
                        ],
                    }
                )

    for seed in range(2, 7):
        for arm in ("control", "extra"):
            for iid in ("TEACH-SRU-01", "TEACH-SRU-02"):
                path = runs["selected_item_report"] / (
                    f"seed{seed}-{arm}-{iid.lower()}-item-report-raw.json"
                )
                report = json.loads(path.read_bytes())["report"]
                table = next(t for t in report["tables"] if t["name"] == "ItemResults")
                columns = [column["name"] for column in table["columns"]]
                rows = [row for instance in table["instances"] for row in instance["rows"]]
                check(len(rows) == 72, "72 selected ItemResults bins")
                check(
                    all(
                        row[columns.index("IID")] == iid
                        and row[columns.index("STID")] == "BASE-01"
                        for row in rows
                    ),
                    "selected item and station identity",
                )
                check(
                    all(
                        rows[i][columns.index("STINT")] == i * 0.5
                        and rows[i][columns.index("ETINT")] == (i + 1) * 0.5
                        for i in range(72)
                    ),
                    "contiguous half-hour grid",
                )

    check(
        extras_total == 15
        and len(groups) == 6
        and sum(len(group["events"]) for group in groups) == 13,
        "15 extra removals, six groups and 13 repeated-position events",
    )
    if CHECKS != 300:
        raise AssertionError(f"stable independent check count: {CHECKS}")
    result = {
        "schema": "simlox-e14-var03-independent-focused-replay/v1",
        "passed": True,
        "verdict": "GO_BOUNDED_DERIVED",
        "checks_passed": CHECKS,
        "checks_total": CHECKS,
        "parent_source_records": len(index["source"]),
        "parent_raw_seals": raw_count,
        "extra_removal_counts": counts,
        "repeat_group_count": len(groups),
        "repeat_event_count": sum(len(group["events"]) for group in groups),
        "repeat_groups": groups,
        "limits": (
            "Read-only catalog mapping of the existing fixed-seed joint RRF/NFFF panel. "
            "No new native run, isolated factor effect, repeat probability, general stock rule, "
            "or full E14/Issue #18 acceptance."
        ),
    }
    (HERE / "independent-verdict.json").write_bytes(
        (json.dumps(result, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    )
    print(
        json.dumps(
            {
                "verdict": result["verdict"],
                "checks": CHECKS,
                "groups": len(groups),
                "repeat_events": result["repeat_event_count"],
            }
        )
    )


if __name__ == "__main__":
    main()
