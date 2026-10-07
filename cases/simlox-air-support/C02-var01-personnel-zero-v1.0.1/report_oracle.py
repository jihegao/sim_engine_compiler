"""Source/event-derived oracle for every cell of the six native report tables."""
from __future__ import annotations

from math import isfinite

DESCRIPTION = "C02.var01 one-step joint request: P-CREW capacity zero, E-GSE capacity one; fixed-seed prospective child"
OLD_DESCRIPTION = "A01/A02 generic one-aircraft teaching case; no J35/F35 equivalence"
SUMMARY_COLUMNS = "NREP RTILW RTIUP MTMF RSMTMF MSTF RSMSTF MSUF RSMSUF STMF RSSTMF".split()
SYSTEM_COLUMNS = "UNID SID STINT ETINT NSYRY NSYMA NSYMO NSYMC NSYMP NSYMT NSYMS NSYMR NSYUA NSYA NSYAL FTMO NSYRP NSYPM NSYTP NSYWR NSYWI NSYLA NSYUH NREPT NPMT NFAIL NDAM NPMS NROBT NRCFG STREQ STACC STF STLOW SYDT SYDTU NSYDT NSYSW NPSTA NPSUC".split()
STOCK_COLUMNS = "STINT ETINT NBO NBOU ROS ROST WT WTT WTS PNB NDF NDD NDR NDP NLD NWT".split()
RESOURCE_COLUMNS = "RID STID STINT ETINT NR NRMO NRMA NRUM NRLA NRW NRA NRN NRF NRRI NRRT NRRO".split()
TOTAL_COLUMNS = "RID STID NR NRMO NRMA NRUM NRLA NRW NRA NRN NRF NRRI NRRT NRRO".split()
SHAPE = {"ProblemDescription": (1, 1), "ResultSummary": (1, 11),
         "SystemResults": (72, 40), "StockTotalResults": (72, 16),
         "ResourceResults": (72, 16), "ResourceResultsTotal": (1, 14)}
INSTANCE = {"ProblemDescription": "", "ResultSummary": "",
            "SystemResults": "Total over all Units;Total over all Systems;0.00;36.00",
            "StockTotalResults": "0.00;36.00;",
            "ResourceResults": "Total over all Resources;Total over all Stations;0.00;36.00",
            "ResourceResultsTotal": "Total over all Resources;Total over all Stations;0.00;36.00"}
COLUMNS = {"ProblemDescription": ["PDESC"], "ResultSummary": SUMMARY_COLUMNS,
           "SystemResults": SYSTEM_COLUMNS, "StockTotalResults": STOCK_COLUMNS,
           "ResourceResults": RESOURCE_COLUMNS, "ResourceResultsTotal": TOTAL_COLUMNS}


def exposure(start: float, end: float, left: float, right: float) -> float:
    assert 0 <= start <= end <= 36
    return max(0.0, min(right, end) - max(left, start)) / (right - left)


def expected(control: bool, cancellation: float | None = None) -> dict[str, list[dict]]:
    if not control:
        assert cancellation is not None and 7 < cancellation <= 8 + 1 / 3
    summary = dict(zip(SUMMARY_COLUMNS, [1, 0, 36, int(control), 0, int(control), 0,
                                         int(control), 0, int(control), 0]))
    system = []
    stock = []
    resource = []
    for i in range(72):
        left, right = i / 2, (i + 1) / 2
        assigned = exposure(7, 10 if control else cancellation, left, right)
        work_or_wait = exposure(7, 7.5 if control else cancellation, left, right)
        mission = exposure(8, 10, left, right) if control else 0
        s = {c: 0 for c in SYSTEM_COLUMNS}
        s.update(UNID="Total over all Units", SID="Total over all Systems",
                 STINT=left, ETINT=right, NSYRY=1 - assigned,
                 NSYMA=assigned, NSYMO=mission,
                 NSYMP=work_or_wait,
                 NSYMR=exposure(7.5, 8, left, right) if control else 0,
                 NSYA=1, FTMO=mission, STACC=mission,
                 SYDT=None, NPSTA=1 if i == 14 else 0,
                 NPSUC=1 if control and i == 15 else 0)
        system.append(s)
        t = {c: 0 for c in STOCK_COLUMNS}
        t.update(STINT=left, ETINT=right, NBOU=None, ROS=None, ROST=None,
                 WT=None, WTT=None, WTS=None, PNB=1)
        stock.append(t)
        r = {c: 0 for c in RESOURCE_COLUMNS}
        capacity = 2 if control else 1
        r.update(RID="Total over all Resources", STID="Total over all Stations",
                 STINT=left, ETINT=right, NR=capacity, NRA=capacity, NRN=capacity,
                 NRUM=2 * work_or_wait if control else 0,
                 NRW=0 if control else work_or_wait)
        resource.append(r)
    capacity = 2 if control else 1
    total = {c: 0 for c in TOTAL_COLUMNS}
    total.update(RID="Total over all Resources", STID="Total over all Stations",
                 NR=capacity, NRA=capacity, NRN=capacity,
                 NRUM=1 / 36 if control else 0,
                 NRW=0 if control else (cancellation - 7) / 36)
    return {"ProblemDescription": [{"PDESC": OLD_DESCRIPTION if control else DESCRIPTION}],
            "ResultSummary": [summary], "SystemResults": system,
            "StockTotalResults": stock, "ResourceResults": resource,
            "ResourceResultsTotal": [total]}


def _time_uncertainty(token: str) -> float:
    # Preserve native's printed decimal places; float(str(token)) loses trailing zeros.
    if "e" in token.lower() or not token.replace(".", "", 1).isdigit():
        raise AssertionError("unsupported scientific printed event time")
    places = len(token.partition(".")[2])
    return 0.5 * 10 ** -places


def cell_bound(table: str, field: str, predicted: object, cancellation_token: str | None) -> float:
    if type(predicted) not in (int, float) or predicted == 0:
        return 0
    if field in ("STINT", "ETINT"):
        return 0
    if float(predicted).is_integer():
        return 0
    if field in ("NSYRY", "NSYMA", "NSYMP", "NRW") and table in ("SystemResults", "ResourceResults"):
        assert cancellation_token is not None
        bound = _time_uncertainty(cancellation_token) / 0.5 + 5e-7
        assert bound <= 2.1e-5
        return bound
    if table == "ResourceResultsTotal" and field in ("NRW", "NRUM"):
        bound = (0 if cancellation_token is None else _time_uncertainty(cancellation_token) / 36) + 5e-7
        assert bound <= 1e-6
        return bound
    raise AssertionError(f"unclassified fractional cell {table}.{field}={predicted}")


def check_report(report: dict, control: bool, cancellation: float | None,
                 cancellation_token: str | None = None) -> int:
    if not control:
        assert cancellation_token is not None and float(cancellation_token) == cancellation
    expected_rows = expected(control, cancellation)
    tables = report["report"]["tables"]
    assert [t["name"] for t in tables] == list(SHAPE)
    comparisons = 0
    for table in tables:
        name = table["name"]
        columns = [column["name"] for column in table["columns"]]
        assert columns == COLUMNS[name], name
        assert len(table["instances"]) == 1
        instance = table["instances"][0]
        assert instance["instance_name"] == INSTANCE[name], name
        rows = instance["rows"]
        assert (len(rows), len(columns)) == SHAPE[name]
        for idx, (values, predicted) in enumerate(zip(rows, expected_rows[name])):
            assert len(values) == len(columns)
            for field, actual in zip(columns, values):
                wanted = predicted[field]
                assert type(actual) is not bool
                if type(wanted) in (float, int):
                    assert type(actual) in (float, int) and isfinite(actual), (name, idx, field, actual)
                    bound = cell_bound(name, field, wanted, cancellation_token)
                    assert abs(actual - wanted) <= bound, (name, idx, field, actual, wanted, bound)
                else:
                    assert actual == wanted, (name, idx, field, actual, wanted)
                comparisons += 1
    assert comparisons == 5210
    return comparisons
