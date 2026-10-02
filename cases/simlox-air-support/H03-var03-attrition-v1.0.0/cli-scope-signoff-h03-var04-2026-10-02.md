# H03.var04 subsequent missions after loss — shared evidence sign-off, 2026-10-02

**Decision:** Accept the bounded later-mission outcome using the same two sealed H03.var03 native runs and source contract. This is a follow-on observation, not an independent native experiment or new isolated source delta. Issue #18 remains open.

The control is byte-identical to accepted H03.var01 mode and repairs its position FM after each in-flight damage event. It launches the three scheduled missions at h8, h20 and h32 and returns ready after each half-hour direct CM task. The attrition child changes the FM damage consequence to `PROB=0`, adds certain `BATTLE-HIT` `<ATTRITION>`, and loses the sole aircraft at h8.13665 during its first mission. That mission aborts and finishes aborted at h8.27329.

The next missions are ordered, created and activated at h19 and h31. Each waits for a system, then cancels at h20.3333 and h32.3333. Neither allocates an aircraft or launches. The 72-bin System report remains lost through horizon36 and ends lost1/ready0, while the control ends lost0/ready1. Stock has no demand or backorder in either arm. The [author replay](validate_native.py) checks cancellation times and absence of later starts; the independent read-only replay under `review/` passes 6,561/6,561 assertions including those event and ledger relationships. The [evidence index](evidence-index.json) binds both runs and 24 local raw seals.

This observation covers one aircraft, one fixed three-mission schedule, seed1 and no replacement or reconstitution. It does not establish a universal post-loss scheduling rule, other resource configurations, GUI visual behavior or cross-engine parity.
