"""Replay source-sealed J03 negative distribution diagnostics without SIMLOX."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT / "tools"))
import validate_native as native  # noqa: E402
import build  # noqa: E402

RUNS = ("j03-pfac-sum-probe-20261001-01", "j03-cycle-probe-20261001-01", "j03-cycle-probe-20261001-02")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path: Path) -> dict:
    return json.loads(native.remove_trailing_commas(path.read_bytes()))


def validate() -> dict:
    errors: list[str] = []
    details: list[dict] = []
    contract = load(HERE / "probe-contract.json")
    diff = load(HERE / "probe-diff.json")
    outputs, expected_diff = build.build()
    if (HERE / "probe-diff.json").read_bytes() != expected_diff:
        errors.append("builder diff differs")
    for name, raw in outputs.items():
        if (HERE / name).read_bytes() != raw:
            errors.append(f"builder input differs: {name}")
    if sha(HERE / "probe-diff.json") != contract["probe_diff_sha256"]:
        errors.append("probe diff fingerprint differs")
    for run_id in RUNS:
        run = HERE / "runs" / run_id
        arm = "pfac-sum" if "pfac-sum" in run_id else "cycle"
        seq = 2 if run_id.endswith("-02") else 1
        runner = HERE / ("probe_native_ssh.ps1" if seq == 2 else "review/probe_native_ssh_initial.ps1")
        parent = build.PARENTS[arm][0]
        invocation, closure = load(run / "invocation.json"), load(run / "closure.json")
        if (invocation.get("schema"), invocation.get("arm"), invocation.get("run_id")) != (
            "simlox-j03-negative-distribution-probe-invocation/ssh-cli-v1", arm, run_id
        ):
            errors.append(f"{run_id}: invocation identity")
        if (closure.get("schema"), closure.get("arm"), closure.get("run_id"), closure.get("state")) != (
            "simlox-j03-negative-distribution-probe-closure/v1", arm, run_id, "native_steps_complete"
        ):
            errors.append(f"{run_id}: closure identity/state")
        if invocation.get("session_id") != 0 or "sshd.exe" not in invocation.get("ssh_ancestor_names", []):
            errors.append(f"{run_id}: SSH provenance")
        if invocation.get("gui_pid") != 13340 or invocation.get("gui_start_utc") != "2026-09-28T10:09:56.8261381Z" or invocation.get("queue_mutex") != "Global\\SimloxIssue18NativeQueue":
            errors.append(f"{run_id}: GUI/mutex identity")
        if invocation.get("input_sha256") != contract["arms"][arm]["input_sha256"] or sha(run / "input.json") != invocation.get("input_sha256"):
            errors.append(f"{run_id}: input SHA")
        if closure.get("invocation_sha256") != sha(run / "invocation.json"):
            errors.append(f"{run_id}: invocation seal")
        sources = {
            "probe-contract.json": HERE / "probe-contract.json",
            "probe-diff.json": HERE / "probe-diff.json",
            "build.py": HERE / "build.py",
            "probe_native_ssh.ps1": runner,
            "pfac-sum-input.json": HERE / "pfac-sum-input.json",
            "cycle-input.json": HERE / "cycle-input.json",
            "parent-input.json": parent,
            "database-dictionary.txt": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\Table relations\DatabaseDictionary_SIMLOX.txt"),
            "manual.pdf": Path(r"C:\Program Files\Systecon\SIMLOX\UserDoc\SIMLOX.pdf"),
        }
        if set(closure.get("post_source_sha256", {})) != set(sources):
            errors.append(f"{run_id}: source set")
        for key, path in sources.items():
            if closure.get("post_source_sha256", {}).get(key) != sha(path):
                errors.append(f"{run_id}: source seal {key}")
        if invocation.get("runner_sha256") != sha(runner) or invocation.get("builder_sha256") != sha(HERE / "build.py") or invocation.get("contract_sha256") != sha(HERE / "probe-contract.json"):
            errors.append(f"{run_id}: invocation source seal")
        raw = closure.get("raw", {})
        for name, record in raw.items():
            path = run / name
            if not path.is_file() or path.stat().st_size != record.get("bytes") or sha(path) != record.get("sha256"):
                errors.append(f"{run_id}: raw seal {name}")
        required = {"input.json", "roundtrip-raw.json", "model.sxi", "model.sxo", "import.log", "export.log", "run.log", "steps.json"}
        if set(raw) - (required | {"model.log"}) or not required.issubset(raw):
            errors.append(f"{run_id}: raw file set")
        roundtrip = native.compare_roundtrip(run / "input.json", run / "roundtrip-raw.json")
        if not roundtrip["all_equal"]:
            errors.append(f"{run_id}: business roundtrip")
        steps = load(run / "steps.json")
        if [step.get("name") for step in steps] != ["import", "export", "calc"] or not all(step.get("coexisting_gui_present_after") is True for step in steps):
            errors.append(f"{run_id}: step/GUI set")
        if [step.get("exit_code") for step in steps[:2]] != [0, 0]:
            errors.append(f"{run_id}: import/export exit")
        sxo_bytes = (run / "model.sxo").stat().st_size
        if sxo_bytes != 4:
            errors.append(f"{run_id}: expected empty 4-byte sxo")
        log = (run / "run.log").read_text(encoding="utf-8-sig", errors="replace")
        if arm == "pfac-sum":
            if steps[2].get("exit_code") != 0 or not re.search(r"\(error #265\) The sum of PFAC does not add up to 1\.0", log):
                errors.append(f"{run_id}: PFAC error #265 missing")
            if not re.search(r"Input conversion completed\. Errors: 1, Warnings: 2, Notes: 0", log):
                errors.append(f"{run_id}: PFAC conversion summary")
            if sorted(re.findall(r"\(warning #(\d+)\)", log)) != ["108", "126"]:
                errors.append(f"{run_id}: PFAC warnings")
        else:
            if steps[2].get("exit_code") != -1073741571 or log or (run / "model.log").exists():
                errors.append(f"{run_id}: cyclic-reference crash signature")
            temp = [p for p in run.iterdir() if re.fullmatch(r"\$\d+@model\.sxi\$", p.name)]
            if len(temp) != 1 or temp[0].stat().st_size <= 4:
                errors.append(f"{run_id}: native temporary file signature")
        details.append({
            "run_id": run_id, "arm": arm, "calc_exit_code": steps[2].get("exit_code"),
            "input_sha256": sha(run / "input.json"), "invocation_sha256": sha(run / "invocation.json"),
            "closure_sha256": sha(run / "closure.json"), "runner_sha256": sha(runner),
            "raw_seal_count": len(raw), "sxo_bytes": sxo_bytes,
            "temporary_files": {p.name: {"bytes": p.stat().st_size, "sha256": sha(p)} for p in run.iterdir() if re.fullmatch(r"\$\d+@model\.sxi\$", p.name)},
        })
    return {
        "schema": "simlox-j03-negative-distribution-author-diagnostics/v1",
        "passed": not errors, "differences": errors, "runs": details,
        "classification": {
            "J03.var05": "one PFAC-sum 0.9 model rejected by native converter error #265; accepted input-test boundary candidate",
            "J03.var06": "same cyclic-reference model caused native calculation child stack overflow 0xC00000FD in two fresh probes; capability limitation, no accepted simulation behavior",
        },
    }


def main() -> None:
    result = validate()
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    output = HERE / "review/author-diagnostics-2026-10-01.json"
    if output.exists() and output.read_bytes() != raw:
        raise ValueError("frozen author diagnostics changed")
    if not output.exists():
        output.write_bytes(raw)
    print(json.dumps({"passed": result["passed"], "differences": result["differences"], "runs": len(result["runs"]), "raw_seals": sum(x["raw_seal_count"] for x in result["runs"])}))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
