"""Check the planning catalog's references and evidence boundaries, not simulation behavior."""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_FAMILY_COUNTS = {"A": 18, "B": 5, "C": 10, "D": 16, "E": 15,
                          "F": 4, "G": 12, "H": 3, "I": 7, "J": 9, "K": 9}
EXPECTED_CASE_IDS = {f"{family}{number:02d}"
                     for family, count in EXPECTED_FAMILY_COUNTS.items()
                     for number in range(1, count + 1)}


def canonical_hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(",", ":")).encode("utf-8")).hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def unique(rows: list[dict], key: str) -> dict[str, dict]:
    result = {row[key]: row for row in rows}
    require(len(result) == len(rows), f"duplicate {key}")
    return result


def check(root: Path = ROOT, *, verify_local_sources: bool = False) -> dict:
    catalog = json.loads((root / "catalog-v2.json").read_text(encoding="utf-8"))
    coverage = json.loads((root / "manual-coverage-v2.json").read_text(encoding="utf-8"))
    sources = json.loads((root / "manual-sources-v2.json").read_text(encoding="utf-8"))
    legacy = json.loads((root / "catalog.json").read_text(encoding="utf-8"))
    require(catalog["schema"] == "simlox-progressive-catalog/v2", "unknown catalog schema")
    require(coverage["schema"] == "simlox-manual-coverage/v2", "unknown coverage schema")
    require(sources["schema"] == "simlox-manual-sources/v2", "unknown source schema")
    require(catalog["legacy_catalog_canonical_sha256"] == canonical_hash(legacy), "legacy catalog changed")
    cases = unique(catalog["cases"], "case_id")
    methods = unique(coverage["methods"], "method_id")
    srcs = unique(sources["sources"], "source_id")
    inventory = unique(coverage["input_table_inventory"], "table")
    require(catalog["case_count"] == len(cases) == len(EXPECTED_CASE_IDS) == 108,
            "wrong case count")
    require(set(cases) == EXPECTED_CASE_IDS, "wrong 108-case identity set")
    require(catalog["extension_case_count"] == len(cases) - 26, "wrong extension count")
    require(catalog["core_case_count"] == len(legacy["cases"]) == 26, "original 26 cases missing")
    require(coverage["method_count"] == len(methods) == 108, "wrong method count")
    require(set(methods) == {f"M-{case_id}" for case_id in EXPECTED_CASE_IDS},
            "wrong 108-method identity set")
    require(len(inventory) == coverage["input_table_count"] == 133, "input table inventory incomplete")
    require(set(inventory) == set(sources["dictionary_table_names"]), "table inventory differs from frozen dictionary names")
    require({c["case_id"] for c in catalog["cases"] if c["core_case"]}
            == {c["case_id"] for c in legacy["cases"]}, "core identities changed")

    for old in legacy["cases"]:
        current = cases[old["case_id"]]
        for field in ("version", "status", "verified_features", "cross_engine_status", "artifact_ref"):
            require(current[field] == old[field], f"{old['case_id']}: evidence promotion in {field}")
        if old["case_id"] in ("A01", "A02"):
            for field in old:
                require(current[field] == old[field], f"{old['case_id']}: frozen entry changed: {field}")

    variants: set[str] = set()
    referenced_methods: set[str] = set()
    for cid, c in cases.items():
        require(c["minimal_configuration"] and c["acceptance_plan"], f"{cid}: missing proposed behavior")
        require(c["method_ids"] and c["boundary_variants"], f"{cid}: missing methods/variants")
        require(c["publication_state"] == "not_published", f"{cid}: planning cannot publish a case")
        expected_capability = ("explicit_mission_type_v1_planned" if cid == "B03"
                               else "manual_documented_native_verification_required")
        require(c["capability_state"] == expected_capability, f"{cid}: unsupported capability promotion")
        if not c["core_case"]:
            require(c["status"] == "planned" and c["version"] is None
                    and not c["verified_features"] and c["artifact_ref"] is None
                    and c["cross_engine_status"] == "unverified", f"{cid}: new case has unsupported evidence")
        require({dep.split("@", 1)[0] for dep in c["requires"]}
                == set(c["instructional_prerequisites"]), f"{cid}: inconsistent prerequisites")
        require(c["case_kind"] in {"modeling_method", "integrated_business_scenario",
                                  "experiment_and_observation", "native_authoring_workflow"},
                f"{cid}: unknown case kind")
        for dep in c["instructional_prerequisites"]:
            require(dep in cases and dep != cid, f"{cid}: invalid prerequisite {dep}")
        parent = c["parent_case"]
        if parent:
            parent = parent.split("@", 1)[0]
            require(parent in cases, f"{cid}: missing parent {parent}")
            require(parent in c["instructional_prerequisites"], f"{cid}: parent absent from prerequisite graph")
        for mid in c["method_ids"]:
            require(mid in methods and methods[mid]["primary_case_id"] == cid, f"{cid}: incorrect method {mid}")
            referenced_methods.add(mid)
        for v in c["boundary_variants"]:
            require(v["variant_id"] not in variants, "duplicate variant ID")
            variants.add(v["variant_id"])
            require(v["status"] == "planned" and v["version"] is None and v["planned_delta"],
                    f"{cid}: variant missing plan-only boundary")
    require(referenced_methods == set(methods), "unreferenced method")
    require(catalog["variant_count"] == len(variants) == 579, "wrong variant count")

    b03 = cases["B03"]
    b03_method = methods["M-B03"]
    require(b03.get("contract_profile") == "explicit-mission-type-v1",
            "B03: wrong explicit mission type contract")
    require("COLD-FIRST" in b03["minimal_configuration"]
            and "HOT-SORTIE" in b03["minimal_configuration"],
            "B03: explicit mission types missing")
    require(set(b03_method["input_tables"]) == {"MissionType", "MissionPreparation",
                                                  "OperationProfile", "Tasks", "TaskBreakDown"}
            and "MissionTurnround" not in b03_method["input_tables"]
            and "MissionPreparation.TID" in b03_method["checked_fields"],
            "B03: mission type mapping incomplete")
    require({"B02", "A02"} <= set(b03["instructional_prerequisites"]),
            "B03: repeated-mission prerequisite missing")
    require(any("同一 MTID" in value and "仍未确认" in value
                for value in b03["limitations"])
            and any("不声称" in value for value in b03["limitations"])
            and any("同一 MTID" in value and "仍未确认" in value
                    for value in b03_method["limitations"]),
            "B03: historical auto-trigger boundary missing")

    c03 = cases["C03"]
    c03_method = methods["M-C03"]
    require({"C02", "A03"} <= set(c03["instructional_prerequisites"]),
            "C03: formation prerequisite missing")
    require(all(value in c03["minimal_configuration"]
                for value in ("需求2架", "07:30", "每架30分钟")),
            "C03: two-aircraft contention contract missing")
    require(any("2人" in value and "08:00" in value and "1人" in value and "08:30" in value
                for value in c03["acceptance_plan"]),
            "C03: launch-time contrast missing")
    require("SubTaskResource" in c03_method["input_tables"]
            and "SystemDeployment" in c03_method["input_tables"]
            and "TaskResource" not in c03_method["input_tables"]
            and "MissionFormation" not in c03_method["input_tables"],
            "C03: first-batch native table mapping mismatch")
    require(any("设备争用" in value and "不能替代" in value for value in c03["limitations"]),
            "C03: unrelated equipment probe boundary missing")

    visiting: set[str] = set()
    done: set[str] = set()

    def visit(cid: str) -> None:
        require(cid not in visiting, f"prerequisite cycle through {cid}")
        if cid in done:
            return
        visiting.add(cid)
        for dep in cases[cid]["instructional_prerequisites"]:
            visit(dep)
        visiting.remove(cid)
        done.add(cid)

    for cid in cases:
        visit(cid)
    for mid, m in methods.items():
        require(m["source_id"] in srcs, f"{mid}: missing source")
        require(m["coverage_state"] == "mapped_to_acceptance_plan", f"{mid}: coverage/evidence conflated")
        require(m["native_scope_state"] == "unverified_for_full_method", f"{mid}: unsupported native method evidence")
        limit = srcs[m["source_id"]]["page_count"]
        require(m["pdf_pages"], f"{mid}: missing manual pages")
        for start, end in m["pdf_pages"]:
            require(1 <= start <= end <= limit, f"{mid}: invalid page range")
        for table in m["input_tables"]:
            require(table in inventory, f"{mid}: unknown table {table}")
        for field in m["checked_fields"]:
            require(field.count(".") == 1 and field.split(".")[0] in m["input_tables"],
                    f"{mid}: field absent from table mapping: {field}")
    for table, row in inventory.items():
        actual = sorted(mid for mid, m in methods.items() if table in m["input_tables"])
        require(actual and actual == row["method_ids"], f"{table}: missing/stale method mapping")
    for row in coverage["scenario_concept_inventory"] + coverage["official_example_inventory"]:
        require(row["case_ids"], f"{row['title']}: uncovered section")
        require(all(cid in cases for cid in row["case_ids"]), f"{row['title']}: unknown case")
    if verify_local_sources:
        for source in sources["sources"]:
            path = Path(source["local_path_hint"])
            require(path.is_file(), f"source unavailable: {path}")
            require(hashlib.sha256(path.read_bytes()).hexdigest() == source["sha256"],
                    f"source fingerprint mismatch: {path}")
        dictionary = Path(srcs["SIMLOX-2017-TABLE-DICTIONARY"]["local_path_hint"])
        rows = list(csv.reader(dictionary.read_text(encoding="utf-8-sig").splitlines(), delimiter=";"))[1:]
        require({row[0] for row in rows} == set(inventory), "local dictionary table mismatch")
        native_fields = {f"{row[0]}.{row[2]}" for row in rows}
        for mid, m in methods.items():
            require(set(m["checked_fields"]) <= native_fields, f"{mid}: field absent from local dictionary")
    return {"scope": "catalog consistency only; no native behavior or conformance run",
            "cases": len(cases), "core_cases": 26, "methods": len(methods),
            "input_tables": len(inventory), "planned_variants": len(variants),
            "local_source_hashes_checked": verify_local_sources}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--verify-local-sources", action="store_true")
    args = parser.parse_args()
    print(json.dumps(check(verify_local_sources=args.verify_local_sources), ensure_ascii=True, indent=2))
