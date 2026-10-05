# E15.var10 independent static preflight

**GO for one guarded, diagnostic-only negative run.** No native process was
launched during this review. The intended run directory did not exist.

The accepted E15 explicit-three parent input and sign-off, E02 prerequisite
input and sign-off, builder, checker, candidate input, contract, installed
SIMLOX executable, and manual all match their ten literal SHA-256 pins.
The contract SHA-256 is
`8a62ccdb15322ef0fa53f97d36da95eb550c8a8e91e3bfb17d22fd1c4094e6c9`;
the candidate input SHA-256 is
`7ca2f1179edba26db4105e41d8988f4e9137dffa1451dfaa23f22b05247fceeb`.
Python syntax for the builder and roundtrip checker parses. The PowerShell
runner parses with zero AST errors; its SHA-256 is
`e13e05e7c6590e48eb168797c4a34ac2148c57903bce05a8fab67b7109b16b61`.

An independent JSON comparison found 31 source tables and exactly one
changed cell: `StockAllocation` row
`[AIR_BASIC, TEACH-DU-01, DEPOT-01]` has `ROSIZ` 2→6; `STSIZ` remains 4.
There are 21 authored row-containing tables. Installed manual physical
page 517 states that the reorder point must be at least −1, so `ROSIZ`
cannot exceed `STSIZ+1`; this case exceeds the bound by one.

The runner requires session-0 SSH with an `sshd.exe` ancestor, an unused
fixed run ID, a nonblocking global native mutex, and active protected GUI
PID 13340/session 1/start identity. It starts hidden CLI children, applies
a 60-second watchdog only after confirming child PID, executable,
session and command-line identity, and checks GUI identity after each step.
It pins source hashes before and after, requires exact import/export of all
21 authored populated tables before calculation, and seals the raw files
in an immutable closure. For the negative gate it requires an explicit
converter error naming the target ROSIZ row and no nonempty simulation
output. Other outcomes remain excluded diagnostics. No report or positive
simulation timeline is claimed.

The expected converter diagnostic is a hypothesis. Native exit behavior,
exact error code and text, and rejection must be reviewed from the sealed
run before any bounded publication claim.
