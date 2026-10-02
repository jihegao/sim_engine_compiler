"""Print compact child versus accepted E08 parent report observations."""
from pathlib import Path

from check_roundtrip import parse_native

HERE = Path(__file__).resolve().parent
PARENT = HERE.parent / "E08-var01-immediate-lateral-v1.0.2" / "runs"


def table_rows(path, name):
    report = parse_native(path)["report"]
    table = next(t for t in report["tables"] if t["name"] == name)
    columns = [col["name"] for col in table["columns"]]
    return [dict(zip(columns, row)) for instance in table["instances"] for row in instance["rows"]]


for station in ("base01", "base02", "depot"):
    child = HERE / "runs" / f"i02-var08-{station}-report-v100-ssh-20261002-01" / "item-report-raw.json"
    control = PARENT / f"e08-on-{station}-report-v102-ssh-20261002-01" / "item-report-raw.json"
    current = table_rows(child, "ItemResults")
    prior = table_rows(control, "ItemResults")
    print(station, "rows", len(current), "early", [
        {k: r[k] for k in ("STINT", "STSZ", "STOHA", "NBO")}
        for r in current if r["STINT"] in (1.5, 2, 2.5, 9.5, 10, 10.5, 11, 14, 35.5)
    ])
    print("first changed bins", [(i / 2, {k: (a[k], b[k]) for k in a if a[k] != b[k]})
                                 for i, (a, b) in enumerate(zip(prior, current)) if a != b][:12])

child = HERE / "runs" / "i02-var08-lateral-out-v100-ssh-20261002-01" / "report-raw.json"
control = PARENT / "e08-immediate-on-v102-ssh-20261002-01" / "report-raw.json"
for name in ("ResultSummary", "SystemResults", "StockTotalResults"):
    a, b = table_rows(control, name), table_rows(child, name)
    print(name, "rows", len(a), len(b), "first changed", [(i, {k: (x[k], y[k]) for k in x if x[k] != y[k]})
                                                         for i, (x, y) in enumerate(zip(a, b)) if x != y][:8])
