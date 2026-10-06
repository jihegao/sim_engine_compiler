"""Build the C02.var03 read-only evidence index after independent replay GO."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
ACCEPTED = HERE.parent / "C02-joint-resources-v1.0.2"
EXCLUDED = HERE.parent / "C02-var03-both-sufficient-v0.1.0"
RAW = Path("C:/Users/user/dev/sim_engine_compiler-b02-v102/cases/simlox-air-support/C02-joint-resources-v1.0.2/runs")
CONTRACT_SHA = "97bf1d7392aa8b3b5c626b737193fec42485e31604f791614bd22b6d8e904a9d"


def pin(path: Path) -> dict:
    data = path.read_bytes()
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def included(path: Path) -> bool:
    return (path.is_file() and path.name != "evidence-index.json"
            and "__pycache__" not in path.parts and path.suffix != ".pyc"
            and not path.name.startswith(("independent-publication-", "independent-staged-", "independent-remote-")))


def local_sources(package: Path, base: Path) -> list[dict]:
    return [{"path": path.relative_to(base).as_posix(), **pin(path)}
            for path in sorted(package.rglob("*")) if included(path)]


def accepted_sources(contract) -> list[dict]:
    prefix = ACCEPTED.relative_to(REPO).as_posix()
    listed = subprocess.run(["git", "ls-files", "--", prefix], cwd=REPO,
                            capture_output=True, text=True, check=True).stdout.splitlines()
    if len(listed) != 18:
        raise ValueError(f"accepted C02 tracked source count {len(listed)} != 18")
    exception = contract["accepted_source"]["published_local_byte_exception"]
    result = []
    for relative in listed:
        path = REPO / relative
        blob = subprocess.run(["git", "show", f"HEAD:{relative.replace(chr(92), '/')}"],
                              cwd=REPO, capture_output=True, check=True).stdout
        local = path.read_bytes()
        name = path.relative_to(ACCEPTED).as_posix()
        if name == ".gitignore":
            if not (pin(path) == {"bytes": exception["local_crlf_bytes"], "sha256": exception["local_sha256"]}
                    and len(blob) == exception["published_git_lf_bytes"]
                    and hashlib.sha256(blob).hexdigest() == exception["published_git_sha256"]
                    and local.replace(b"\r\n", b"\n") == blob):
                raise ValueError("accepted .gitignore disk/Git byte exception differs")
        elif local != blob:
            raise ValueError(f"accepted disk/Git source bytes differ: {relative}")
        result.append({"path": name, "local_disk": pin(path),
                       "published_git": {"bytes": len(blob), "sha256": hashlib.sha256(blob).hexdigest()}})
    return result


def accepted_runs(contract) -> list[dict]:
    result = []
    for role, arm in contract["accepted_source"]["arms"].items():
        input_path = ACCEPTED / arm["input"]
        run = RAW / arm["run_id"]
        closure_path = run / "closure.json"
        if pin(input_path)["sha256"] != arm["input_sha256"] or pin(closure_path)["sha256"] != arm["closure_sha256"]:
            raise ValueError(f"accepted {role} input/closure pin differs")
        closure = load(closure_path)
        invocation_path = run / "invocation.json"
        if (closure["run_id"] != arm["run_id"] or len(closure["raw"]) != 11
                or pin(invocation_path)["sha256"] != closure["invocation_sha256"]):
            raise ValueError(f"accepted {role} run/invocation seal differs")
        for name, seal in closure["raw"].items():
            if pin(run / name) != {"bytes": seal["bytes"], "sha256": seal["sha256"]}:
                raise ValueError(f"accepted {role} raw seal differs: {name}")
        result.append({"role": role, "run_id": arm["run_id"], "input": {"path": arm["input"], **pin(input_path)},
                       "local_run_dir": str(run), "closure": pin(closure_path),
                       "invocation": pin(invocation_path), "raw": closure["raw"]})
    return result


def build():
    contract_path = HERE / "contract.json"
    if pin(contract_path)["sha256"] != CONTRACT_SHA:
        raise ValueError("corrected contract hash differs")
    contract = load(contract_path)
    for name, key in (("contract.json", "contract_sha256"),
                      ("review/independent-readonly-2026-09-29.json", "original_independent_report_sha256"),
                      ("evidence-2026-09-29.md", "evidence_report_sha256")):
        if pin(ACCEPTED / name)["sha256"] != contract["accepted_source"][key]:
            raise ValueError(f"accepted source pin differs: {name}")
    if pin(EXCLUDED / "contract.json")["sha256"] != "03a0381bce2dd60013709f8acbda0041d5e10c0887414ed2e9edf71b93e6ff34":
        raise ValueError("excluded v0.1.0 contract differs")
    if pin(EXCLUDED / "review/independent-contract-2026-10-07.md")["sha256"] != "381d65f09678f26177efb8fa5417014dbda18fca2865d3cf17433c24a3b7ceec":
        raise ValueError("excluded v0.1.0 NO_GO differs")
    author = load(HERE / "author-validation.json")
    reviewer = load(HERE / "review/independent-verdict.json")
    if (author.get("decision") != "GO_BOUNDED" or author.get("checks_total") != 28139
            or author.get("checks_passed") != 28139 or author.get("raw_seals") != 44 or author.get("failures")):
        raise ValueError("author replay gate differs")
    if (reviewer.get("decision") != "GO_BOUNDED" or reviewer.get("checks_total") != reviewer.get("checks_passed")
            or reviewer.get("raw_seals") != 44 or reviewer.get("report_cells_each") != 5210 or reviewer.get("failures")):
        raise ValueError("independent replay gate differs")
    runs = accepted_runs(contract)
    if sum(len(run["raw"]) for run in runs) != 44:
        raise ValueError("expected 44 reused raw seals")
    return {
        "schema": "simlox-c02-var03-both-sufficient-evidence-index/v1",
        "case_id": "C02", "variant_id": "C02.var03", "version": "0.1.1",
        "status": "bounded_read_only_classification_ready_for_publication",
        "publication_state": "not_published", "new_native_run_count": 0,
        "source": local_sources(HERE, HERE),
        "excluded_diagnostic_source": local_sources(EXCLUDED, HERE.parent),
        "accepted_source": {"package": ACCEPTED.name, "files": accepted_sources(contract)},
        "runs": runs, "reused_raw_count": 44,
        "author_checks": author["checks_passed"],
        "independent_verdict": {"path": "review/independent-verdict.json", **pin(HERE / "review/independent-verdict.json")},
        "scope": "One fixed-seed accepted four-run comparison of single INSPECT30 versus serial INSPECT10+SERVICE20 with joint P-CREW/E-GSE sufficiency and matched device-zero controls.",
        "limits": "No new native, isolated single-cell topology effect, general task-topology equivalence or resource law, GUI visual, cross-engine or full Issue18 claim.",
        "raw_location_policy": "accepted_external_local_only_ignored_runs_not_committed"
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    result = build()
    raw = (json.dumps(result, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    destination = HERE / "evidence-index.json"
    if args.write:
        if destination.exists():
            raise FileExistsError(destination)
        destination.write_bytes(raw)
    elif not destination.exists() or destination.read_bytes() != raw:
        raise ValueError("frozen evidence index missing or differs; independent reviewer must finish before --write")
    print(json.dumps({"index_sha256": hashlib.sha256(raw).hexdigest(),
                      "source_files": len(result["source"]), "reused_raw_count": result["reused_raw_count"],
                      "new_native_run_count": 0}))


if __name__ == "__main__":
    main()
