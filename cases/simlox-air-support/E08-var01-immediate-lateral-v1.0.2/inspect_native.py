"""Print compact native report observations for E08 author analysis."""
from pathlib import Path

from check_roundtrip import parse_native

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"


def table_rows(path, name):
    report = parse_native(path)["report"]
    table = next(t for t in report["tables"] if t["name"] == name)
    columns = [col["name"] for col in table["columns"]]
    return [dict(zip(columns, row)) for instance in table["instances"] for row in instance["rows"]]


for variant in ("on", "off"):
    print(variant)
    for station, label in (("base01", "BASE-01"), ("base02", "BASE-02"), ("depot", "DEPOT-01")):
        path = RUNS / f"e08-{variant}-{station}-report-v102-ssh-20261002-01" / "item-report-raw.json"
        rows = table_rows(path, "ItemResults")
        selected = [{key: row[key] for key in ("STINT", "ETINT", "STSZ", "STOHA", "NBO")}
                    for row in rows if 9.5 <= row["STINT"] <= 11.5]
        print(label, "rows", len(rows), "near-first-shortage", selected,
              "terminal", {key: rows[-1][key] for key in ("STSZ", "STOHA", "NBO")})

for name in ("ResultSummary", "SystemResults", "StockTotalResults", "MissionResults"):
    left = table_rows(RUNS / "e08-on-base01-report-v102-ssh-20261002-01" / "item-report-raw.json", name)
    right = table_rows(RUNS / "e08-off-base01-report-v102-ssh-20261002-01" / "item-report-raw.json", name)
    print("comparison", name, "row counts", len(left), len(right))
    print("first differences", [(i, {k: (a[k], b[k]) for k in a if a[k] != b[k]}) for i, (a, b) in enumerate(zip(left, right)) if a != b][:8])
