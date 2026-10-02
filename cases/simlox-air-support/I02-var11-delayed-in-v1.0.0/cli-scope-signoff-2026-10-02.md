# I02.var11 bounded CLI signoff — delayed scheduled IN

**Accepted contrast:** The child changes only `ItemTransfer.TFDT` 0→2 hours
and `ProblemDescription` in accepted I02.var01 tracked one-unit IN to
`DEPOT-01` at h4. Its source SHA-256 is
`7d520331ee6233a83600ff711247ec66f15d362a4f377e96a59e0d5a4b6f751c`;
the accepted parent SHA-256 is
`85ee84d85e610f753215882fca59cc3331a9ce0f3313ae635f2a7422e8abcf4d`;
the exact-diff SHA-256 is
`f6f99a352705c0bc443ad7e51ea3e67a2a096d02f508813e17efebe6c3fc5f82`.
The other 30 source tables are identical. The installed manual's TFDT prose
is inconsistent on IN applicability; the native observation resolves this
specific installed-version case.

The guarded session-0 SSH run
`i02-var11-in-delay2-v100-ssh-20261002-01` preserved GUI PID 13340,
completed five native steps, converted with zero errors, exactly round-tripped
22 populated authored tables, and produced a nonempty SXO. The sealed-SXO
report-only run `i02-var11-depot-item-v100-ssh-20261002-01` produced 72
half-hour depot ItemResults rows. The two closures seal 14 local raw files;
the proprietary report selector and raw files remain local, ignored by Git.

The native log starts one IN task at h4 with transfer time two hours, then
records physical item ID 1 arriving and entering depot stock at h6. Depot
`ItemResults.STSZ` and `STOHA` remain 1 in h4–6 bins and become 2 at h6.
Against the accepted TFDT0 parent, only the four h4, h4.5, h5 and h5.5
ItemResults rows differ, only in those two columns. At h10 the depot issues
pre-existing ID 0 for ordinary demand; on-hand falls to 1 while nominal stays
2. Failed ID 2 repairs and returns at h13.1667. Mission, system, stock total
and summary tables match the parent. `ItemResultsTotal` stock values are
36-hour averages: nominal 68/36 in the parent and 66/36 in the child.

Author read-only replay passed 41/41 checks. Separate independent read-only
replay passed 439/439, checked all 14 raw seals and returned bounded GO. Its
checker and exact verdict are recorded under `review/` and indexed in
`evidence-index.json`.

**Boundary:** One IN, one IID/depot, TFDT 0 versus 2, one seed and this CLI.
The downstream demand occurs after both arrivals, so shortage competition,
other delays, OUT, BETWEEN, reorder, procurement, GUI visual behavior and
cross-engine parity remain unverified. I02 and Issue #18 remain open.
