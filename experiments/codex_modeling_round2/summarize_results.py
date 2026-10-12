"""Post-score reporting only. Preserves the frozen scorer and its raw results."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def read(path):
    return json.loads((ROOT / path).read_text())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    (ROOT / path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def compact(row):
    keys = ["arm", "repeat", "task_id", "category", "candidate_status", "accepted",
            "baseline_accepted", "compiled", "executed", "assessment_kind",
            "initial_screen_passed", "answered", "end_to_end_screen_and_model_passed", "error"]
    result = {key: row[key] for key in keys if key in row}
    result["failed_check_ids"] = [x["id"] for x in row.get("checks", []) if not x["passed"]]
    result["interventions"] = [{"id": x["id"], "accepted": x["accepted"]}
                               for x in row.get("interventions", [])]
    return result


def main():
    raw = read("results/raw/main/summary.json")
    summary = {k: v for k, v in raw.items() if k not in ("primary", "followups")}
    summary["source"] = {"path": "results/raw/main/summary.json",
                         "sha256": sha(ROOT / "results/raw/main/summary.json"),
                         "availability": "results/evidence.tar.gz"}
    summary["primary"] = [compact(x) for x in raw["primary"]]
    summary["followups"] = [compact(x) for x in raw["followups"]]
    write("results/summary.json", summary)
    write("results/repair-summary.json", read("results/raw/repair/summary.json"))

    mapping = read("review/blind-mapping.json")
    blind = read("review/blind-semantic-review.json")
    reviews = blind["reviews"]
    assert len(reviews) == len(mapping) == 72
    assert {x["review_id"] for x in reviews} == set(mapping)
    scored = {(x["arm"], x["repeat"], x["task_id"]): x for x in raw["primary"]}
    mapped = []
    for review in reviews:
        identity = mapping[review["review_id"]]
        auto = scored[tuple(identity[k] for k in ("arm", "repeat", "task_id"))]
        mapped.append({**identity, **review, "category": auto["category"],
                       "automatic_screen_passed": auto["accepted"]})
    text_summary = {"reviewer": blind["reviewer"], "method": blind["method"],
                    "expected": 72, "semantic_passed": sum(x["semantically_correct"] for x in mapped),
                    "by_arm": {}, "reviews": mapped,
                    "disagreements": [x for x in mapped if x["automatic_screen_passed"] != x["semantically_correct"]]}
    for arm in "ABC":
        text_summary["by_arm"][arm] = {}
        for category in ("clarify", "unsupported"):
            rows = [x for x in mapped if x["arm"] == arm and x["category"] == category]
            text_summary["by_arm"][arm][category] = {"expected": 12,
                "automatic_screen_passed": sum(x["automatic_screen_passed"] for x in rows),
                "semantic_passed": sum(x["semantically_correct"] for x in rows)}
    write("results/text-review-summary.json", text_summary)

    frozen = {}
    for name in ("frozen-inputs.json", "repair-frozen-inputs.json"):
        data = read(name)
        failed = [p for p, expected in data["sha256"].items() if sha(ROOT / p) != expected]
        assert not failed, failed
        frozen[name] = {"files": len(data["sha256"]), "all_hashes_match": True}
    source = read("source-manifest.json")
    for entry in source["files"]:
        data = (ROOT.parent.parent / entry["path"]).read_bytes()
        assert hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest() == entry["git_blob_sha"]

    log = read("controller-log.json")
    for key, expected_count in (("primary_sha256", 216), ("followup_sha256", 36)):
        assert len(log[key]) == expected_count
        assert all(sha(ROOT / p) == value for p, value in log[key].items())
    runs = []
    for stage in ("submissions", "followups"):
        for path in sorted((ROOT / stage).glob("*/*/log.json")):
            data = json.loads(path.read_text())
            begin, end = data["started_at_utc"], data["finished_at_utc"]
            seconds = (datetime.fromisoformat(end) - datetime.fromisoformat(begin)).total_seconds()
            calls, revisions = len(data.get("validation_calls", [])), len(data.get("revisions", []))
            arm, repeat = path.parent.parent.name, path.parent.name
            assert calls == ((16 if stage == "submissions" else 4) if arm == "C" else 0)
            assert revisions == 0
            if arm == "C":
                attempts = sorted((path.parent / "attempts").glob("Q*-v0.json"))
                assert len(attempts) == (24 if stage == "submissions" else 4)
                assert sum(json.loads(p.read_text())["status"] == "model" for p in attempts) == calls
                assert all(sha(p) == sha(path.parent / (p.stem.removesuffix("-v0") + ".json")) for p in attempts)
            runs.append({"stage": stage, "arm": arm, "repeat": repeat,
                         "self_reported_start_utc": begin, "self_reported_end_utc": end,
                         "self_reported_wall_seconds": seconds, "validation_calls": calls,
                         "revisions": revisions, "log_sha256": sha(path)})
    assert len(runs) == 18
    repair_equal = {}
    for arm in "NDT":
        files = sorted((ROOT / "repair/submissions" / arm / "r1").glob("R*.json"))
        repair_equal[arm] = {"count": len(files), "r2_equals_r1": all(
            p.read_bytes() == (p.parent.parent / "r2" / p.name).read_bytes() for p in files)}
        assert len(files) == 6 and repair_equal[arm]["r2_equals_r1"]
    audit = {"recorded_at_utc": datetime.now(timezone.utc).isoformat(),
             "frozen_inputs": frozen, "engine_source_blobs_verified": len(source["files"]),
             "primary_seals_verified": 216, "followup_seals_verified": 36,
             "runs": runs, "repair_revision_identity": repair_equal,
             "model_id": None, "tokens": None, "cost": None,
             "limitations": ["Shared filesystem: access restrictions were instructions, not OS enforcement.",
                 "File reads, call counts and start/end times are participant-reported; C v0/final byte identity was verified.",
                 "Wall limits were not forcibly enforced. Logged main durations were below 1800 seconds.",
                 "Dispatch and per-agent receipt latency were not fully instrumented; logs do not measure pure inference time.",
                 "Blind semantic reviewer is an AI with inherited session settings, not a human or different-model judge."]}
    write("results/audit.json", audit)
    log["main_completions"] = [x for x in runs if x["stage"] == "submissions"]
    log["followup_dispatches"] = [{"arm": p.parent.parent.name, "repeat": p.parent.name,
        "primary_sealed_and_answers_prepared_at_utc": json.loads(p.read_text())["sealed_at_utc"],
        "dispatch_timestamp": None, "record": str(p.relative_to(ROOT))}
        for p in sorted((ROOT / "followup-prompts").glob("*/*/controller-record.json"))]
    log["post_score_notes"] = [
        "Completion times are participant-reported, appended during final audit; exact controller receipts are unavailable.",
        "Follow-up seal/preparation times are not dispatch times; follow-up batches were sent after each run's primary seal.",
        "prepare_followup.py and repair/replay.py were added as controller wrappers after input freezes; original contracts unchanged.",
        "summarize_results.py and package_evidence.py are post-score reporting utilities, not frozen grading inputs.",
        "Main replay exited 1 for three automatic unsupported concept-screen failures; raw scores were preserved."]
    write("controller-log.json", log)
    print(json.dumps({"primary": len(summary["primary"]), "followups": len(summary["followups"]),
                      "blind_reviews": len(mapped), "screen_disagreements": len(text_summary["disagreements"]),
                      "frozen": frozen, "sources": len(source["files"]), "runs": len(runs)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
