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
    pm_starts = find(r"^\s*system PM task \d+ on <HOME-AIR,\d+> started")
    candidates = [e for e in pm_starts if e.time == 9 and "<HOME-AIR,2>" in e.text]
    assert len(candidates) == 1, "unique source-scheduled HOME-PM9"
    pm_start = candidates[0]
    pm_task = int(re.search(r"system PM task (\d+)", pm_start.text).group(1))
    pm_id = one(rf"^\s*system PM task {pm_task} on <HOME-AIR,2> PMID: HOME-PM9")
    assert "<HOME-AIR,2>" in pm_start.text and "<HOME-AIR,2>" in pm_id.text
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
    wait_starts = [e for e in find(r"<HOME-AIR,2> nbr resourcewait increased") if e.time == pm_start.time]
    assert len(wait_starts) == 1
    wait_start = wait_starts[0]
    later_wait_ends = [e for e in find(r"<HOME-AIR,2> nbr resourcewait decreased")
                       if (e.time,e.line) > (wait_start.time,wait_start.line)]
    assert later_wait_ends
    wait_end = later_wait_ends[0]
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
    for _,a,b,_ in returning:
        planned = re.search(r"transportation time:\s*(0\.125|0\.5)(?:\s|$)", a.text)
        assert planned, ("unlisted return time", a)
        assert duration(a.time, b.time, float(planned.group(1)))
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
    # Every observed loan cycle needs its own borrower request, repair owner,
    # release and return. Repeated task IDs or cross-cycle attribution fail.
    linked_repairs = set()
    matched_allocations = set()
    matched_deallocations = set()
    previous_return = (-1.0, -1)
    for o_start, o_arrive, r_start, r_arrive, _, _ in cycles:
        releases = [e for e in find(r"direct repair subtask \d+ seqno 1 within system DIRP task \d+ on <TEACH-AIR-01,\d+> frees resources")
                    if (o_arrive.time,o_arrive.line) < (e.time,e.line) < (r_start.time,r_start.line)]
        assert releases, ("loan has no linked repair release", o_start.time)
        cycle_bookings = [e for e in find(r"direct repair subtask \d+ seqno 1 within system DIRP task \d+ on <TEACH-AIR-01,\d+> books resources")
                          if (o_arrive.time,o_arrive.line) < (e.time,e.line) < (r_start.time,r_start.line)]
        assert len(cycle_bookings) == len(releases), "each loan repair books and releases once"
        last_release = (o_arrive.time,o_arrive.line)
        for repair_index, release_event in enumerate(releases):
            identity = re.search(r"subtask (\d+) seqno 1 within system DIRP task (\d+) on <TEACH-AIR-01,(\d+)>", release_event.text)
            assert identity
            task_key = tuple(map(int, identity.groups()))
            assert task_key not in linked_repairs, "repair reused across loan cycles"
            linked_repairs.add(task_key)
            subtask, repair_task, owner = task_key
            prefix = rf"direct repair subtask {subtask} seqno 1 within system DIRP task {repair_task} on <TEACH-AIR-01,{owner}>"
            repair_start = [e for e in ev if re.search(rf"^\s*system DIRP task {repair_task} on <TEACH-AIR-01,{owner}> started", e.text)]
            repair_done = [e for e in ev if re.search(rf"^\s*system DIRP task {repair_task} on <TEACH-AIR-01,{owner}> completed", e.text)]
            subtask_done = [e for e in ev if re.search(prefix + r" completed", e.text)]
            booked = [e for e in ev if re.search(prefix + r" books resources", e.text)]
            performed = [e for e in ev if re.search(prefix + r" starts performing", e.text)]
            assert len(repair_start) == len(repair_done) == len(subtask_done) == len(booked) == len(performed) == 1
            assert (repair_start[0].time,repair_start[0].line) < (booked[0].time,booked[0].line)
            assert (booked[0].time,booked[0].line) < (performed[0].time,performed[0].line) < (subtask_done[0].time,subtask_done[0].line)
            assert last_release < (booked[0].time,booked[0].line)
            assert (subtask_done[0].time,subtask_done[0].line) < (release_event.time,release_event.line) < (repair_done[0].time,repair_done[0].line) < (r_start.time,r_start.line)
            allocations = [e for e in find(r"<P-MECH at <BASE-01,\d+>> allocated to maintenance task:\s*1")
                           if e.time == booked[0].time and booked[0].line < e.line < performed[0].line]
            deallocations = [e for e in find(r"<P-MECH at <BASE-01,\d+>> deallocated from\s+maintenance task:\s*1")
                             if e.time == release_event.time and release_event.line < e.line < repair_done[0].line]
            assert len(allocations) == len(deallocations) == 1, ("typed borrower booking/release", task_key)
            assert allocations[0].line not in matched_allocations and deallocations[0].line not in matched_deallocations
            matched_allocations.add(allocations[0].line)
            matched_deallocations.add(deallocations[0].line)
            if repair_index == 0:
                failed = [e for e in ev if re.search(prefix + r" resource availability test", e.text) and
                          re.search(r"<P-MECH at <BASE-01,\d+>> request for:\s*1 failed", e.text) and
                          previous_return < (e.time,e.line) < (o_start.time,o_start.line)]
                assert len(failed) == 1, ("loan request identity", task_key, len(failed))
                assert (repair_start[0].time,repair_start[0].line) <= (failed[0].time,failed[0].line)
            last_release = (deallocations[0].time,deallocations[0].line)
        previous_return = (r_arrive.time,r_arrive.line)
    assert len(linked_repairs) == len(find(r"direct repair subtask \d+ seqno 1 within system DIRP task \d+ on <TEACH-AIR-01,\d+> frees resources"))
    # Other PM tasks may occur later. They must have unique task identities,
    # bare subtask work edges and matching completion; the report oracle checks
    # all state and resource intervals, including terminal closure.
    pm_groups = {}
    for start in pm_starts:
        identity = re.search(r"system PM task (\d+) on <HOME-AIR,(\d+)>", start.text)
        assert identity
        key = tuple(map(int, identity.groups()))
        assert key not in pm_groups
        pm_groups[key] = start
    for (task_id, owner), start in pm_groups.items():
        completions = [e for e in ev if re.search(rf"^\s*system PM task {task_id} on <HOME-AIR,{owner}> completed", e.text)]
        performed = [e for e in ev if re.search(rf"subtask \d+ seqno 1 within system PM task {task_id} on <HOME-AIR,{owner}> starts performing", e.text)]
        finished = [e for e in ev if re.search(rf"subtask \d+ seqno 1 within system PM task {task_id} on <HOME-AIR,{owner}> completed", e.text)]
        booked = [e for e in ev if re.search(rf"subtask \d+ seqno 1 within system PM task {task_id} on <HOME-AIR,{owner}> books resources", e.text)]
        freed = [e for e in ev if re.search(rf"subtask \d+ seqno 1 within system PM task {task_id} on <HOME-AIR,{owner}> frees resources", e.text)]
        assert len(completions) == len(performed) == len(finished) == len(booked) == len(freed) == 1
        assert (booked[0].time,booked[0].line) < (performed[0].time,performed[0].line)
        assert (start.time,start.line) < (performed[0].time,performed[0].line) < (finished[0].time,finished[0].line) <= (completions[0].time,completions[0].line)
        pm_allocations = [e for e in find(r"<P-MECH at <BASE-02,\d+>> allocated to maintenance task:\s*1")
                          if e.time == booked[0].time and booked[0].line < e.line < performed[0].line]
        pm_deallocations = [e for e in find(r"<P-MECH at <BASE-02,\d+>> deallocated from\s+maintenance task:\s*1")
                            if e.time == freed[0].time and freed[0].line < e.line < completions[0].line]
        assert len(pm_allocations) == len(pm_deallocations) == 1, ("typed HOME PM booking/release", task_id)
        assert pm_allocations[0].line not in matched_allocations and pm_deallocations[0].line not in matched_deallocations
        matched_allocations.add(pm_allocations[0].line)
        matched_deallocations.add(pm_deallocations[0].line)
    all_allocations = find(r"<P-MECH at <BASE-0[12],\d+>> allocated to maintenance task:\s*1")
    all_deallocations = find(r"<P-MECH at <BASE-0[12],\d+>> deallocated from\s+maintenance task:\s*1")
    assert {e.line for e in all_allocations} == matched_allocations, "orphan P-MECH allocation"
    assert {e.line for e in all_deallocations} == matched_deallocations, "orphan P-MECH deallocation"
    remote_pool_arrivals = find(r"<P-MECH at <BASE-01,\d+>> remote transport arrives: 1")
    home_pool_arrivals = find(r"<P-MECH at <BASE-02,\d+>> return transport arrives: 1")
    assert len(remote_pool_arrivals) == len(outward) and len(home_pool_arrivals) == len(returning)
    for _,out_arrive,_,return_arrive,_,_ in cycles:
        assert sum(e.time == out_arrive.time and e.line == out_arrive.line + 1
                   for e in remote_pool_arrivals) == 1, "typed BASE-01 receipt must follow its arrival"
        assert sum(e.time == return_arrive.time and e.line == return_arrive.line + 1
                   for e in home_pool_arrivals) == 1, "typed BASE-02 receipt must follow its arrival"
    qualifying = [(o,a,r,z,o_id,r_id) for o,a,r,z,o_id,r_id in cycles
                  if any((a.time,a.line) < (req.time,req.line) < (r.time,r.line) and
                         (wait_start.time,wait_start.line) <= (r.time,r.line) and
                         (z.time,z.line) <= (wait_end.time,wait_end.line)
                         for req in request)]
    assert qualifying, "no lender-shortage-attributed return"
    assert any(duration(r.time, z.time, expected) and
               re.search(rf"transportation time:\s*{expected:g}(?:\s|$)", r.text) and
               z.time <= perform.time for _,_,r,z,_,_ in qualifying), "TTRSS return duration"
    assert not find(r"(?:Stock initiated|Replacement item arrives|Take replacement item|Put back replacement item)"), "unexpected item stock"
    assert len(qualifying) == 1, "ambiguous shortage-attributed return"
    out_start, out_arrive, return_start, return_arrive, outward_id, return_id = qualifying[0]
    releases = [e for e in find(r"direct repair subtask \d+ seqno 1 within system DIRP task \d+ on <TEACH-AIR-01,\d+> frees resources")
                if (out_arrive.time,out_arrive.line) < (e.time,e.line) < (return_start.time,return_start.line)]
    assert len(releases) == 1
    release = releases[0]
    base_deallocations = [e for e in find(r"<P-MECH at <BASE-01,\d+>> deallocated from\s+maintenance task:\s*1")
                          if release.time == e.time and release.line < e.line < return_start.line]
    assert len(base_deallocations) == 1
    base_deallocation = base_deallocations[0]
    assert (release.time, release.line) < (base_deallocation.time, base_deallocation.line) < (return_start.time, return_start.line)
    pm_book = one(rf"subtask {pm_subtask} seqno 1 within system PM task {pm_task} on <HOME-AIR,2> books resources")
    pm_free = one(rf"subtask {pm_subtask} seqno 1 within system PM task {pm_task} on <HOME-AIR,2> frees resources")
    bookings = [e for e in find(r"<P-MECH at <BASE-02,\d+>> allocated to maintenance task:\s*1")
                if e.time == pm_book.time and pm_book.line < e.line < perform.line]
    deallocations = [e for e in find(r"<P-MECH at <BASE-02,\d+>> deallocated from\s+maintenance task:\s*1")
                     if e.time == pm_free.time and pm_free.line < e.line < complete.line]
    assert len(bookings) == len(deallocations) == 1
    home_booking, home_deallocation = bookings[0], deallocations[0]
    assert (return_arrive.time, return_arrive.line) < (home_booking.time, home_booking.line) <= (perform.time, perform.line)
    assert (subtask_complete.time, subtask_complete.line) < (home_deallocation.time, home_deallocation.line)
    special_home_boundary_valid = (pm_start.time == wait_start.time == 9 and wait_end.time > 9.5 and
                                   all(req.time == 9 for req in request))
    return {"pm_started":pm_start.time,"pm_wait_started":wait_start.time,"pm_work_started":perform.time,
            "pm_completed":complete.time,"pm_task_id":pm_task,"pm_subtask_id":pm_subtask,
            "outward_count":len(outward),"return_count":len(returning),
            "outward_start":out_start.time,"outward_arrival":out_arrive.time,
            "return_start":return_start.time,"return_start_line":return_start.line,
            "return_arrival":return_arrive.time,
            "outward_task_id":outward_id,"return_task_id":return_id,
            "special_home_boundary_valid":special_home_boundary_valid,
            "qualifying_return_task_ids":[r_id for *_,r_id in qualifying],
            "qualifying_return_hours":[round(z.time-r.time,6) for _,_,r,z,_,_ in qualifying]}

