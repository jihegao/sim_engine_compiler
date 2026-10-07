"""Read-only typed transport, lender wait and PM ledger for either arm."""
from __future__ import annotations
import re
from report_oracle import events
from numeric_bounds import printed_time_uncertainty

def physical(log: str, arm: str) -> dict:
    ev = events(log)
    uncertainty = printed_time_uncertainty(log)
    def duration(first: float, last: float, expected: float) -> bool:
        return abs(last - first - expected) <= uncertainty[first] + uncertainty[last] + 1e-12
    def find(pattern: str) -> list:
        return [e for e in ev if re.search(pattern, e.text)]
    def one(pattern: str):
        found = find(pattern)
        assert len(found) == 1, (pattern, len(found))
        return found[0]
    assert len(find(r"HOME-UNIT.*mission (ordered|created|activated|starting)")) == 0
    pm_start = one(r"^\s*system PM task \d+ on <HOME-AIR,\d+> started")
    pm_id = one(r"^\s*system PM task \d+ on <HOME-AIR,\d+> PMID: HOME-PM9")
    assert "<HOME-AIR,2>" in pm_start.text and "<HOME-AIR,2>" in pm_id.text
    pm_task = int(re.search(r"system PM task (\d+)", pm_start.text).group(1))
    assert int(re.search(r"system PM task (\d+)", pm_id.text).group(1)) == pm_task
    assert abs(pm_start.time - 9) < 0.0002 and pm_id.time == pm_start.time
    request = [e for e in ev if re.search(rf"within system PM task {pm_task} on <HOME-AIR,\d+>", e.text) and
               "resource availability test" in e.text and
               re.search(r"<P-MECH at <BASE-02,\d+>> request for:\s*1 failed", e.text)]
    assert request, "HOME P-MECH failed availability not observed"
    assert all("<HOME-AIR,2>" in e.text for e in request)
    request_subtasks = {int(re.search(r"subtask (\d+) seqno", e.text).group(1)) for e in request}
    assert len(request_subtasks) == 1
    pm_subtask = next(iter(request_subtasks))
    wait_start = one(r"<HOME-AIR,\d+> nbr resourcewait increased")
    wait_end = one(r"<HOME-AIR,\d+> nbr resourcewait decreased")
    assert "<HOME-AIR,2>" in wait_start.text and "<HOME-AIR,2>" in wait_end.text
    assert request[0].time <= wait_start.time <= wait_end.time
    perform = one(rf"subtask {pm_subtask} seqno 1 within system PM task {pm_task} on <HOME-AIR,\d+> starts performing")
    subtask_complete = one(rf"subtask {pm_subtask} seqno 1 within system PM task {pm_task} on <HOME-AIR,\d+> completed")
    complete = one(rf"^\s*system PM task {pm_task} on <HOME-AIR,\d+> completed")
    assert all("<HOME-AIR,2>" in e.text for e in (perform, subtask_complete, complete))
    assert wait_end.time <= perform.time < complete.time <= 12
    assert subtask_complete.time == complete.time
    assert duration(perform.time, complete.time, 0.25)
    def transport(kind: str) -> list[tuple]:
        starts = find(rf"\b{kind} resource transport task \d+ starts with 1 resources")
        arrivals = find(rf"\b{kind} resource transport task \d+ arrives with 1 resources")
        created = find(rf"\b{kind} resource transport task \d+ created:")
        assert starts and len(starts) == len(arrivals) == len(created)
        def keyed(found: list) -> dict[int, object]:
            pairs = [(int(re.search(r"transport task (\d+)", e.text).group(1)), e) for e in found]
            assert len({key for key,_ in pairs}) == len(pairs), kind
            return dict(pairs)
        by_start, by_arrival, by_created = keyed(starts), keyed(arrivals), keyed(created)
        assert set(by_start) == set(by_arrival) == set(by_created), kind
        pairs = [(by_created[key], by_start[key], by_arrival[key], key) for key in by_start]
        assert all((c.time,c.line) < (s.time,s.line) < (a.time,a.line) for c,s,a,_ in pairs)
        source, destination = (("BASE-02", "BASE-01") if kind == "remote" else
                               ("BASE-01", "BASE-02"))
        for created_event, _, _, _ in pairs:
            assert re.search(rf"starting from\s+<P-MECH at <{source},\d+>>\s+aiming for\s+"
                             rf"<P-MECH at <{destination},\d+>>", created_event.text), created_event
        return sorted(pairs, key=lambda x: (x[1].time,x[1].line))
    outward = transport("remote")
    returning = transport("return")
    assert len(outward) == len(returning)
    for _,a,b,_ in outward:
        assert re.search(r"transportation time:\s*0\.25(?:\s|$)", a.text)
        assert duration(a.time, b.time, 0.25)
    expected = 0.5 if arm == "ordinary" else 0.125
    for _,a,_,_ in returning:
        assert re.search(rf"transportation time:\s*{expected:g}(?:\s|$)", a.text)
    # Transport IDs identify the three edges within each task. A return task
    # receives a different ID from its outward task, so associate them through
    # the observed one-unit lender occupancy rather than positional list zip.
    timeline = sorted([(s.time,s.line,"out",(s,a,task_id)) for _,s,a,task_id in outward] +
                      [(s.time,s.line,"return",(s,a,task_id)) for _,s,a,task_id in returning])
    active = None
    cycles = []
    for _, _, kind, (start, arrival, task_id) in timeline:
        if kind == "out":
            assert active is None, "second outward trip before lender unit returned"
            active = (start, arrival, task_id)
        else:
            assert active is not None, "return without an observed outward loan"
            o_start, o_arrive, o_id = active
            assert (o_arrive.time,o_arrive.line) <= (start.time,start.line)
            cycles.append((o_start,o_arrive,start,arrival,o_id,task_id))
            active = None
    assert active is None and len(cycles) == len(outward)
    remote_pool_arrivals = find(r"<P-MECH at <BASE-01,\d+>> remote transport arrives: 1")
    home_pool_arrivals = find(r"<P-MECH at <BASE-02,\d+>> return transport arrives: 1")
    assert len(remote_pool_arrivals) == len(outward) and len(home_pool_arrivals) == len(returning)
    for _,out_arrive,_,return_arrive,_,_ in cycles:
        assert sum(e.time == out_arrive.time and e.line > out_arrive.line for e in remote_pool_arrivals) == 1
        assert sum(e.time == return_arrive.time and e.line > return_arrive.line for e in home_pool_arrivals) == 1
    qualifying = [(o,a,r,z,o_id,r_id) for o,a,r,z,o_id,r_id in cycles
                  if any((a.time,a.line) < (req.time,req.line) < (r.time,r.line) and
                         (wait_start.time,wait_start.line) <= (r.time,r.line) and
                         (z.time,z.line) <= (wait_end.time,wait_end.line)
                         for req in request)]
    assert qualifying, "no lender-shortage-attributed return"
    assert any(duration(r.time, z.time, expected) and
               z.time <= perform.time for _,_,r,z,_,_ in qualifying), "TTRSS return duration"
    assert not find(r"(?:Stock initiated|Replacement item arrives|Take replacement item|Put back replacement item)"), "unexpected item stock"
    assert len(qualifying) == 1, "ambiguous shortage-attributed return"
    out_start, out_arrive, return_start, return_arrive, outward_id, return_id = qualifying[0]
    release = one(r"direct repair subtask \d+ seqno 1 within system DIRP task \d+ on <TEACH-AIR-01,\d+> frees resources")
    base_deallocation = one(r"<P-MECH at <BASE-01,\d+>> deallocated from\s+maintenance task:\s*1")
    assert (release.time, release.line) < (base_deallocation.time, base_deallocation.line) < (return_start.time, return_start.line)
    home_booking = one(r"<P-MECH at <BASE-02,\d+>> allocated to maintenance task:\s*1")
    home_deallocation = one(r"<P-MECH at <BASE-02,\d+>> deallocated from\s+maintenance task:\s*1")
    assert (return_arrive.time, return_arrive.line) < (home_booking.time, home_booking.line) <= (perform.time, perform.line)
    assert (subtask_complete.time, subtask_complete.line) < (home_deallocation.time, home_deallocation.line)
    special_home_boundary_valid = (pm_start.time == wait_start.time == 9 and wait_end.time > 9.5 and
                                   all(req.time == 9 for req in request))
    return {"pm_started":pm_start.time,"pm_wait_started":wait_start.time,"pm_work_started":perform.time,
            "pm_completed":complete.time,"pm_task_id":pm_task,"pm_subtask_id":pm_subtask,
            "outward_count":len(outward),"return_count":len(returning),
            "outward_start":out_start.time,"outward_arrival":out_arrive.time,
            "return_start":return_start.time,"return_arrival":return_arrive.time,
            "outward_task_id":outward_id,"return_task_id":return_id,
            "special_home_boundary_valid":special_home_boundary_valid,
            "qualifying_return_task_ids":[r_id for *_,r_id in qualifying],
            "qualifying_return_hours":[round(z.time-r.time,6) for _,_,r,z,_,_ in qualifying]}

