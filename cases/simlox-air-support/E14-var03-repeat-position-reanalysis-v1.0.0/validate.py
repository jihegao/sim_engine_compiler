"""Focused source-bound replay of accepted E14 repeated-position observations."""

import hashlib
import json
import re
import subprocess
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PARENT = HERE.parent / "E14-var01-02-extra-removal-v1.0.0"
E05 = HERE.parent / "E05-local-repair-reissue-v1.0.0"
CONTRACT = json.loads((HERE / "contract.json").read_text(encoding="utf-8"))
PIN = CONTRACT["accepted_parent"]
CHECKS = 0


def check(condition, label):
    global CHECKS
    CHECKS += 1
    if not condition:
        raise AssertionError(label)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def file_pin(path, expected_sha, expected_size=None):
    data = path.read_bytes()
    check(sha(data) == expected_sha, f"SHA {path}")
    if expected_size is not None:
        check(len(data) == expected_size, f"size {path}")
    return data


check(CONTRACT["case_id"] == "E14" and CONTRACT["variant_id"] == "E14.var03", "contract identity")
commit = PIN["published_commit"]
for path, expected in (
    (PARENT / "cli-scope-signoff-2026-10-05.md", PIN["signoff_git_sha256"]),
    (E05 / "cli-scope-signoff-2026-09-29.md", CONTRACT["prerequisite"]["signoff_git_sha256"]),
    (PARENT / "review" / "independent-verdict.json", PIN["independent_verdict_sha256"]),
):
    blob = subprocess.check_output(["git", "-C", str(ROOT), "show", f"{commit}:" + path.relative_to(ROOT).as_posix()])
    check(sha(blob) == expected, f"published Git byte pin {path}")
local_index = file_pin(PARENT / "evidence-index.json", PIN["evidence_index_local_crlf_sha256"], PIN["evidence_index_local_bytes"])
published_index = subprocess.check_output(["git", "-C", str(ROOT), "show", f"{commit}:" + (PARENT / "evidence-index.json").relative_to(ROOT).as_posix()])
check(sha(published_index) == PIN["evidence_index_published_git_lf_sha256"], "published index SHA")
check(len(published_index) == PIN["evidence_index_published_git_bytes"], "published index size")
check(local_index.replace(b"\r\n", b"\n") == published_index, "CRLF/LF byte relation")
index = json.loads(local_index)
check(index == json.loads(published_index), "parsed index equality")
check(index["raw_files_total"] == 164, "parent raw count")

runs = {}
sealed_count = 0
for kind, run_id_key, closure_key in (
    ("native", "native_run_id", "native_closure_sha256"),
    ("selected_item_report", "selected_report_run_id", "selected_report_closure_sha256"),
):
    spec = index["runs"][kind]
    check(spec["run_id"] == PIN[run_id_key], f"{kind} run ID")
    run = PARENT / "runs" / spec["run_id"]
    file_pin(run / "closure.json", PIN[closure_key], spec["closure"]["bytes"])
    for name, meta in spec["raw"].items():
        file_pin(run / name, meta["sha256"], meta["bytes"])
        sealed_count += 1
    runs[kind] = run
check(sealed_count == 164, "all accepted raw seals")

extra_re = re.compile(r"Time: ([\d.]+).*item SURP task (\d+) on <TEACH-LRU-01,0,(\d+)> extra removal of subitem <(TEACH-SRU-0[12]),0,(\d+)>")
groups = []
event_counts = {}
for seed in range(2, 7):
    for arm in ("control", "extra"):
        text = (runs["native"] / f"seed{seed}-{arm}.log").read_text(encoding="latin-1")
        lines = text.splitlines()
        events = []
        for line_no, line in enumerate(lines):
            match = extra_re.search(line)
            if match:
                time, task, lru, item, removed = match.groups()
                events.append((line_no, float(time), task, lru, item, removed))
        event_counts[f"seed{seed}-{arm}"] = len(events)
        if arm == "control":
            check(not events, f"seed{seed} control has no extras")
            continue
        by_position = defaultdict(list)
        for pos, event in enumerate(events):
            line_no, time, task, lru, item, removed = event
            end = events[pos + 1][0] if pos + 1 < len(events) else len(lines)
            segment_lines = lines[line_no:end]
            demand_positions = [n for n, row in enumerate(segment_lines) if re.search(rf"Item demand arrives.*item requiring maintenance is <{item},0,{removed}>", row)]
            check(len(demand_positions) == 1, f"seed{seed} demand {removed}")
            demand_at = demand_positions[0]
            next_demand = next((n for n in range(demand_at + 1, len(segment_lines)) if "Item demand arrives" in segment_lines[n]), len(segment_lines))
            issues = re.findall(rf"Take replacement item <{item},0,(\d+)> from stock", "\n".join(segment_lines[demand_at:next_demand]))
            check(len(issues) == 1, f"seed{seed} one stock issue {removed}")
            by_position[(task, lru, item)].append((time, removed, issues[0]))
        for (task, lru, item), sequence in by_position.items():
            if len(sequence) < 2:
                continue
            times, removed_ids, issued_ids = zip(*sequence)
            check(all(a < b for a, b in zip(times, times[1:])), f"seed{seed} serial {task}/{item}")
            check(len(set(removed_ids)) == len(sequence), f"seed{seed} distinct removed {task}/{item}")
            check(len(set(issued_ids)) == len(sequence), f"seed{seed} distinct issues {task}/{item}")
            groups.append({"seed": seed, "task": task, "lru_id": lru, "sru_iid": item, "events": sequence})

check(len(groups) == 6, "six observed repeat groups")
check(sum(len(g["events"]) for g in groups) == 13, "13 events in repeat groups")
check(sum(event_counts[f"seed{seed}-extra"] for seed in range(2, 7)) == 15, "15 accepted extra removals")
for seed in range(2, 7):
    for item in ("teach-sru-01", "teach-sru-02"):
        path = runs["selected_item_report"] / f"seed{seed}-extra-{item}-item-report-raw.json"
        report = json.loads(path.read_text(encoding="utf-8-sig"))["report"]
        table = next(t for t in report["tables"] if t["name"] == "ItemResults")
        check(sum(len(i["rows"]) for i in table["instances"]) == 72, f"72 stock bins seed{seed}/{item}")

result = {"schema": "simlox-e14-var03-focused-replay/v1", "verdict": "GO_BOUNDED_DERIVED", "checks": CHECKS,
          "parent_raw_seals": sealed_count, "event_counts": event_counts, "repeat_groups": groups,
          "scope": "Existing accepted joint RRF/NFFF panel only; no new native run or isolated parameter effect"}
(HERE / "review" / "author-verdict.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps({"verdict": result["verdict"], "checks": CHECKS, "groups": len(groups), "repeat_events": 13}))
