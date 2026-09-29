# D01 system-level direct repair, v1.0.0

Status: `native_behavior_accepted_cli_scope`, `reusable_published` for the
restricted [dated sign-off](cli-scope-signoff-2026-09-29.md). This first bounded D01 slice
derives from [published A02](../A02-single-aircraft-repeated-missions/cli-scope-signoff-2026-09-29.md).
It retains one aircraft and three fixed mission opportunities while adding
one operational system failure clock and a fixed 0.5-hour local direct
repair turnaround. The [contract](contract.json) pins the accepted parent, input,
SIMLOX 2017 manual fingerprint and source pages, and acceptance conditions.
The [parent diff](parent-diff.json) has exactly three changed tables.

`System.FRT=300000` with `OPID=OPHOURS` is 0.3 failures per operating hour
under the manual's failures-per-million convention. Failure times are
stochastic; the fixed seed is for repeatability on this executable, not a
hand-selected timestamp. The three scheduled launches are at 8, 20 and 32
hours if the aircraft is available. The sealed native events establish the
observed failures, mission outcomes, repairs and recoveries for this run.

Run `python build.py` to check the frozen input against the parent and
deterministic generator. `python build.py --write` only creates a missing
input and refuses to overwrite it. The sealed native run
`d01-v100-ssh-20260929-01` produced two critical failures, two aborted
missions, two 0.5-hour local repair turnarounds and one successful middle
mission. Author validation passed 293 checks and independent read-only
replay passed with no differences. An installed component, item replacement,
stock and item repair remain separate D01 variants; this first slice cannot
establish them.
