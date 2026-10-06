"""Read-only author classification of accepted serial C02 equipment capacity pair."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
ACCEPTED = HERE.parent / "C02-joint-resources-v1.0.2"
RUN_ROOT = Path("C:/Users/user/dev/sim_engine_compiler-b02-v102/cases/simlox-air-support/C02-joint-resources-v1.0.2/runs")
PINS = {
    "serial-both": ("f7b9c19958d96cdc8a6bf955fd94a52e61b12e6dd116e310683732688dbf550e", "c02-v102-serial-both-ssh-20260929-02", "86c0de86b8494953d39704aafe64f6aab7038e2a649d684a926739b399670c84"),
    "serial-equipment-zero": ("2f209a5420432263b588230624d7586a3edecab2da613efbf65d6a1e8df862fa", "c02-v102-serial-zero-ssh-20260929-02", "79ab8014a50ed3797a537d8395c9ba1a60b97eb27be26b187e5c93860bbe6d64"),
}
CHECKS: dict[str, bool] = {}


def sha_bytes(raw: bytes):
    return hashlib.sha256(raw).hexdigest()


def sha(path: Path):
    return sha_bytes(path.read_bytes())


def check(label: str, passed: bool):
    CHECKS[label] = bool(passed)


def accepted_helper():
    path = ACCEPTED / "review_readonly.py"
    check("accepted reviewer SHA", sha(path) == "331eaad50f2cd7256aa15c800ef8acd7b34551a9d389b85d0b476b207f5a29e5")
    spec = importlib.util.spec_from_file_location("accepted_c02_readonly", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def source_git():
    paths = [p for p in ACCEPTED.rglob("*") if p.is_file() and "runs" not in p.parts and "__pycache__" not in p.parts]
    check("accepted source 18 files", len(paths) == 18)
    for path in paths:
        rel = path.relative_to(ACCEPTED).as_posix()
        blob = subprocess.run(["git", "show", f"HEAD:cases/simlox-air-support/{ACCEPTED.name}/{rel}"], check=True, capture_output=True).stdout
        disk = path.read_bytes()
        if rel == ".gitignore":
            check("accepted .gitignore dual identities", len(disk) == 8 and sha_bytes(disk) == "8d22814e19ac1121bcdcfb89aa88c9da384ec98d2f31f90cedc7a29f95b5f17f" and len(blob) == 7 and sha_bytes(blob) == "127672b43b817aa8f10c44cdb48d4eeef8c0201da894e8a2430cce505ab49933" and disk.replace(b"\r\n", b"\n") == blob)
        else:
            check(f"accepted published {rel}", disk == blob)


def report_rows(doc, name):
    table = next(t for t in doc["report"]["tables"] if t["name"] == name)
    cols = [c["name"] for c in table["columns"]]
    return [dict(zip(cols, row)) for inst in table["instances"] for row in inst["rows"]]


def verify_run(helper, variant: str):
    input_sha, run_id, closure_sha = PINS[variant]
    run = RUN_ROOT / run_id
    check(f"{variant} source SHA", sha(ACCEPTED / "inputs" / f"{variant}.json") == input_sha)
    check(f"{variant} closure SHA", sha(run / "closure.json") == closure_sha)
    errors, detail = helper.run_audit(run, variant)
    check(f"{variant} accepted source/raw/event replay", errors == [] and detail["raw_closure_count"] == 11 and detail["roundtrip_business_tables"] == 17)
    report = helper.read(run / "report-raw.json")
    names = [t["name"] for t in report["report"]["tables"]]
    check(f"{variant} six report tables", names == ["ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults", "ResourceResults", "ResourceResultsTotal"])
    counts = {name: len(report_rows(report, name)) for name in names}
    check(f"{variant} full report rows", counts == {"ProblemDescription": 1, "ResultSummary": 1, "SystemResults": 72, "StockTotalResults": 72, "ResourceResults": 72, "ResourceResultsTotal": 1})
    cells = sum(len(t["columns"]) * sum(len(inst["rows"]) for inst in t["instances"]) for t in report["report"]["tables"])
    check(f"{variant} 5210 cells", cells == 5210)
    for name in ("SystemResults", "StockTotalResults", "ResourceResults"):
        check(f"{variant} {name} complete clock", all(row["STINT"] == i / 2 and row["ETINT"] == (i + 1) / 2 for i, row in enumerate(report_rows(report, name))))
    resource = report_rows(report, "ResourceResults")
    total = report_rows(report, "ResourceResultsTotal")[0]
    success = variant == "serial-both"
    check(f"{variant} report capacity/use", all(r["NR"] == (2 if success else 1) for r in resource) and total["NR"] == (2 if success else 1) and abs(total["NRUM"] - (1 / 108 if success else 0)) < 1e-6)
    check(f"{variant} report wait", all(abs(r["NRW"] - (0 if success else 1 if i == 14 else 1 / 6 if i == 15 else 0)) < 1e-5 for i, r in enumerate(resource)))
    check(f"{variant} report summary", report_rows(report, "ResultSummary")[0]["MSUF"] == int(success))
    check(f"{variant} terminal ready", report_rows(report, "SystemResults")[-1]["NSYRY"] == 1)
    source = helper.read(ACCEPTED / "inputs" / f"{variant}.json")
    return source, report


def main():
    check("contract SHA", sha(HERE / "contract.json") == "475f5d05aec01c27e57cbe2c2afd7fc77e3f60c5dd0e33783b834d7de2b5ba56")
    check("accepted original independent review SHA", sha(ACCEPTED / "review/independent-readonly-2026-09-29.json") == "6a2ee36473b85de15c72fc896375afb050d6cec60572a5fd4e46d64a56af4264")
    source_git()
    helper = accepted_helper()
    check("accepted source audit", helper.source_audit() == [])
    both, good_report = verify_run(helper, "serial-both")
    zero, bad_report = verify_run(helper, "serial-equipment-zero")
    a, b = helper.tables(both, "model"), helper.tables(zero, "model")
    check("sole changed source table", [name for name in a if a[name] != b[name]] == ["ResourceAllocation"])
    ar, br = a["ResourceAllocation"], b["ResourceAllocation"]
    check("sole E-GSE RQTY cell", len(ar) == len(br) == 3 and [(r["RID"], r["RQTY"]) for r in ar] == [("P-CREW", 1), ("P-OTHER", 0), ("E-GSE", 1)] and [(r["RID"], r["RQTY"]) for r in br] == [("P-CREW", 1), ("P-OTHER", 0), ("E-GSE", 0)] and [key for i in range(3) for key in ar[i] if ar[i][key] != br[i][key]] == ["RQTY"])
    check("same report description", report_rows(good_report, "ProblemDescription") == report_rows(bad_report, "ProblemDescription"))
    check("same stock ledger", report_rows(good_report, "StockTotalResults") == report_rows(bad_report, "StockTotalResults"))
    failures = [label for label, passed in CHECKS.items() if not passed]
    result = {"schema": "simlox-c02-var02-author-readonly-reclassification/v1", "decision": "GO_BOUNDED" if not failures else "NO_GO", "passed": not failures, "check_count": len(CHECKS), "failures": failures, "new_native_run_count": 0, "selected_run_ids": [PINS[v][1] for v in PINS]}
    (HERE / "author-validation.json").write_bytes((json.dumps(result, indent=2) + "\n").encode())
    print(json.dumps(result, indent=2))
    return not failures


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
