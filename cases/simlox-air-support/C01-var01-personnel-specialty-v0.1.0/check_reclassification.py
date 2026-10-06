"""Read-only author check of accepted qualified/wrong-specialty C01 runs."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "C01-personnel-capacity-v1.0.2"
RUNS = Path("C:/Users/user/dev/sim_engine_compiler-b02-v102/cases/simlox-air-support/C01-personnel-capacity-v1.0.2/runs")
PINS = {
    "qualified": ("capacity-2", "a0d81fcfd065aa393b7ea9dace2b089e4779077e99cb242a2eae0299318c216c", "c01-v102-cap2-ssh-20260929-05", "770537c9097ba24fbec533d5c6f1eafa29153c18bde63cd0b1bc621a65c55163"),
    "wrong_specialty": ("wrong-specialty", "e1341e7abfc8e1f4c853ba11648c0dfb1de6a90de3341aecae180af8ea4d0783", "c01-v102-wrong-ssh-20260929-03", "610b2b9d12352a9ca06f9241c2d20f824bfa759fffd0a6f202d2ee1b4a44ba8f"),
}
CHECKS: dict[str, bool] = {}


def sha_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def sha(path: Path) -> str:
    return sha_bytes(path.read_bytes())


def check(label: str, passed: bool):
    CHECKS[label] = bool(passed)


def read(path: Path):
    raw = path.read_text(encoding="utf-8-sig")
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Native report has trailing commas. Raw hashes are checked first.
        out = []
        quote = escape = False
        for i, char in enumerate(raw):
            if quote:
                out.append(char)
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == '"':
                    quote = False
            elif char == '"':
                quote = True
                out.append(char)
            elif char == "," and raw[i + 1:].lstrip().startswith(("]", "}")):
                continue
            else:
                out.append(char)
        return json.loads("".join(out))


def tables(doc, envelope="model"):
    return {t["name"]: t for t in doc[envelope]["tables"]}


def rows(doc, name, envelope="model"):
    t = tables(doc, envelope)[name]
    cols = [c["name"] for c in t["columns"]]
    return [dict(zip(cols, row)) for inst in t["instances"] for row in inst["rows"]]


def times(log: str, token: str):
    return [float(m.group(1)) for line in log.splitlines() if token in line and (m := re.match(r"Time:\s*([0-9.]+)", line))]


def near(values, expected):
    return len(values) == len(expected) and all(abs(a - b) < 0.00005 for a, b in zip(values, expected))


def parent_git():
    files = [p for p in PARENT.rglob("*") if p.is_file() and "runs" not in p.parts and "__pycache__" not in p.parts]
    check("18 accepted source files", len(files) == 18)
    for path in files:
        rel = path.relative_to(PARENT).as_posix()
        blob = subprocess.run(["git", "show", f"HEAD:cases/simlox-air-support/{PARENT.name}/{rel}"], check=True, capture_output=True).stdout
        disk = path.read_bytes()
        if rel == ".gitignore":
            check(".gitignore dual byte identities", len(disk) == 8 and sha_bytes(disk) == "8d22814e19ac1121bcdcfb89aa88c9da384ec98d2f31f90cedc7a29f95b5f17f" and len(blob) == 7 and sha_bytes(blob) == "127672b43b817aa8f10c44cdb48d4eeef8c0201da894e8a2430cce505ab49933" and disk.replace(b"\r\n", b"\n") == blob)
        else:
            check(f"published source {rel}", disk == blob)


def run(role: str):
    variant, input_sha, run_id, closure_sha = PINS[role]
    directory = RUNS / run_id
    source_path = PARENT / "inputs" / f"{variant}.json"
    check(f"{role} source SHA", sha(source_path) == input_sha)
    check(f"{role} closure SHA", sha(directory / "closure.json") == closure_sha)
    closure = read(directory / "closure.json")
    invocation = read(directory / "invocation.json")
    check(f"{role} run identity", closure["variant_id"] == variant and closure["run_id"] == run_id and invocation["variant_id"] == variant and invocation["run_id"] == run_id)
    check(f"{role} invocation seal", sha(directory / "invocation.json") == closure["invocation_sha256"])
    check(f"{role} SSH and GUI provenance", invocation["execution_mode"] == "ssh_cli_v1" and invocation["session_id"] == 0 and "sshd.exe" in invocation["ssh_ancestor_names"] and invocation["coexisting_gui"]["pid"] == 13340 and invocation["coexisting_gui"]["session_id"] == 1 and invocation["coexisting_gui"]["process_start_utc"] == "2026-09-28T10:09:56.8261381Z")
    check(f"{role} 11 raw seals", len(closure["raw"]) == 11)
    for name, sealed in closure["raw"].items():
        path = directory / name
        check(f"{role} raw {name}", path.stat().st_size == sealed["bytes"] and sha(path) == sealed["sha256"])
    source = read(source_path)
    native = read(directory / "input.json")
    exported = read(directory / "roundtrip-raw.json")
    check(f"{role} exact native input", source == native)
    authored = {name: rows(source, name) for name, t in tables(source).items() if any(inst["rows"] for inst in t["instances"])}
    substantive = [name for name, rr in authored.items() if any(any(v not in (None, "") for v in row.values()) for row in rr)]
    check(f"{role} 20 rows/17 substantive tables", len(authored) == 20 and len(substantive) == 17)
    for name, rr in authored.items():
        check(f"{role} roundtrip {name}", rr == rows(exported, name))
    check(f"{role} exact two-crew request", len(rows(source, "SubTaskResource")) == 1 and all(rows(source, "SubTaskResource")[0][k] == v for k, v in {"TID": "PREP-FIXED", "SEQ": 1, "RID": "P-CREW", "QTY": 2, "ARID": None}.items()))
    log = (directory / "model.log").read_text(encoding="utf-8-sig")
    check(f"{role} P-CREW request", log.count("Availability test on  <P-CREW at <BASE-01,0>> request for: 2 ") == 1)
    check(f"{role} no P-OTHER request", "Availability test on  <P-OTHER" not in log)
    if role == "qualified":
        for label, token, expected in (("lease", " allocated to maintenance task:", [7]), ("release", " deallocated from  maintenance task:", [7.16667]), ("SEQ1 work", "seqno 1 within system preparation task 0 on <TEACH-AIR-01,0> starts performing", [7]), ("SEQ2 work", "seqno 2 within system preparation task 0 on <TEACH-AIR-01,0> starts performing", [7.16667]), ("launch", " mission starting, duration:", [8]), ("success", " mission success:", [10])):
            check(f"{role} {label}", near(times(log, token), expected))
        check(f"{role} no cancellation", not times(log, " mission cancelled:"))
        check(f"{role} two-person lease", "allocated to maintenance task: 2  available now: 0" in log and "deallocated from  maintenance task: 2  available now: 2" in log)
    else:
        check(f"{role} failed request", "Availability test on  <P-CREW at <BASE-01,0>> request for: 2 failed" in log)
        check(f"{role} no partial booking/work/launch", " books resources" not in log and " allocated to maintenance task:" not in log and " starts performing," not in log and " mission starting, duration:" not in log)
        check(f"{role} cancellation", near(times(log, " mission cancelled:"), [7.58333]))
    report = read(directory / "report-raw.json")
    check(f"{role} six report tables", list(tables(report, "report")) == ["ProblemDescription", "ResultSummary", "SystemResults", "StockTotalResults", "ResourceResults", "ResourceResultsTotal"])
    summary = rows(report, "ResultSummary", "report")
    system = rows(report, "SystemResults", "report")
    stock = rows(report, "StockTotalResults", "report")
    resource = rows(report, "ResourceResults", "report")
    total = rows(report, "ResourceResultsTotal", "report")
    check(f"{role} complete report row counts", (len(summary), len(system), len(stock), len(resource), len(total)) == (1, 72, 72, 72, 1))
    for label, ledger in (("system", system), ("stock", stock), ("resource", resource)):
        check(f"{role} {label} clock", all(r["STINT"] == i / 2 and r["ETINT"] == (i + 1) / 2 for i, r in enumerate(ledger)))
    success = role == "qualified"
    check(f"{role} summary success", summary[0]["MSTF"] == int(success) and summary[0]["MSUF"] == int(success))
    check(f"{role} system timeline", all(r["NPSTA"] == int(i == 14) and r["NPSUC"] == int(success and i == 15) and r["FTMO"] == int(success and 16 <= i < 20) for i, r in enumerate(system)))
    check(f"{role} equal total resource capacity", all(r["NR"] == 2 for r in resource) and total[0]["NR"] == 2)
    check(f"{role} resource busy profile", all(abs(r["NRUM"] - (2 / 3 if success and i == 14 else 0)) < 1e-5 for i, r in enumerate(resource)))
    check(f"{role} resource wait profile", all(abs(r["NRW"] - (2 if not success and i == 14 else 1 / 3 if not success and i == 15 else 0)) < 1e-5 for i, r in enumerate(resource)))
    check(f"{role} resource total ledger", abs(total[0]["NRUM"] - (1 / 108 if success else 0)) < 1e-6 and abs(total[0]["NRW"] - sum(r["NRW"] / 72 for r in resource)) < 1e-6)
    check(f"{role} terminal ready", system[-1]["ETINT"] == 36 and system[-1]["NSYRY"] == 1)
    check(f"{role} zero stock demand", all(r["NBO"] == 0 and r["NDF"] == 0 for r in stock))
    return source, report


def main():
    check("contract SHA", sha(HERE / "contract.json") == "6ccf6608d3b1c86f0463f9414bf890536d81ed4b94c8672a132701c5eb8b377c")
    check("original independent review SHA", sha(PARENT / "review/independent-readonly-2026-09-29.json") == "b8b0bd11bfbde8c84e6e9bf9a4bb82a58da23e3436ce775082265d28c6d31f73")
    old = read(PARENT / "review/independent-readonly-2026-09-29.json")
    check("original independent accepted", old["passed"] is True and old["differences"] == [])
    parent_git()
    qualified, good_report = run("qualified")
    wrong, bad_report = run("wrong_specialty")
    changed = [name for name in tables(qualified) if tables(qualified)[name] != tables(wrong)[name]]
    check("sole changed table", changed == ["ResourceAllocation"])
    qa, ba = rows(qualified, "ResourceAllocation"), rows(wrong, "ResourceAllocation")
    check("exact two RQTY cells", len(qa) == len(ba) == 2 and [(r["RID"], r["RQTY"]) for r in qa] == [("P-CREW", 2), ("P-OTHER", 0)] and [(r["RID"], r["RQTY"]) for r in ba] == [("P-CREW", 0), ("P-OTHER", 2)] and [key for i in range(2) for key in qa[i] if qa[i][key] != ba[i][key]] == ["RQTY", "RQTY"])
    check("same report description", tables(good_report, "report")["ProblemDescription"] == tables(bad_report, "report")["ProblemDescription"])
    check("same stock ledger", tables(good_report, "report")["StockTotalResults"] == tables(bad_report, "report")["StockTotalResults"])
    failures = [label for label, passed in CHECKS.items() if not passed]
    result = {"schema": "simlox-c01-var01-author-readonly-reclassification/v1", "decision": "GO_BOUNDED" if not failures else "NO_GO", "passed": not failures, "check_count": len(CHECKS), "failures": failures, "new_native_run_count": 0, "selected_run_ids": [PINS[key][2] for key in ("qualified", "wrong_specialty")]}
    (HERE / "author-validation.json").write_bytes((json.dumps(result, indent=2) + "\n").encode())
    print(json.dumps(result, indent=2))
    return not failures


if __name__ == "__main__":
    raise SystemExit(0 if main() else 1)
