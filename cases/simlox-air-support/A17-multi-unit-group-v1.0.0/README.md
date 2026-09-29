# A17 two explicit units at two bases, v1.0.0

Status: `native_behavior_accepted_cli_scope`, `reusable_published` for the
bounded recipe in the [dated sign-off](cli-scope-signoff-2026-09-29.md).
This first A17 slice derives
from the [accepted A03 1.0.1 two-aircraft case](../A03-two-aircraft-formation-v1.0.1/cli-scope-signoff-2026-09-29.md).
It keeps the same one-wave, two-aircraft task and divides the aircraft
between `TEACH-UNIT` at `BASE-01` and `TEACH-UNIT-2` at `BASE-02`. The shared
`TEACH-GROUP` owns the operational profile; neither group nor station
represents aircraft movement. Both units are required, so this candidate
does not test priority choice.

The frozen [contract](contract.json) pins the A03 parent input, SIMLOX 2017
manual SHA-256 and physical pages, input SHA-256
`66d3eef1e1cf42d26971af9719feb68e7ec3ecd4ed188a8477f8cbe0918bb974`,
business identities, fixed timeline, CLI assertions and excluded A17
variants. The [parent diff](parent-diff.json) lists the seven changed tables;
all other A03 tables remain byte-equivalent as JSON values. The group and
member columns follow the installed manual's tables on physical PDF pages
310 and 312. The proprietary PDF is not part of this repository.

Run `python build.py` to check the checked input against the pinned parent
and deterministic generator. `python build.py --write` is only for creating
the input once in an empty directory; it refuses to overwrite it.

The [SSH import/export probe](probe_native_ssh.ps1) is a capability probe,
not behavior acceptance. The [four-step native runner](run_native_ssh.ps1)
adds calculation and JSON report export. Both require a fresh run ID, a
session-0 SSH launch, the host-wide native queue, the pinned executable and
the single active GUI PID 13340. They keep raw outputs under ignored
`runs/<run-id>/`, including failed attempts. The [preflight record](preflight-2026-09-29.md)
explains the disconnected-session guard and the first probe checker false
positive. The full candidate `a17-v100-ssh-20260929-01` completed all four
native steps; [author validation](review/author-validation-2026-09-29.json)
passes 281 source-bound checks. Independent read-only replay passed with
no differences. Priority and other A17 variants remain untested.
