# G10.var01 independent static preflight — 2026-10-03

**Verdict: GO for one guarded diagnostic native run.** This is a source and runner review, not a native behavior verdict.

The initial draft was **NO-GO**: `Redundancy.RLID` and `SID` omitted `key: true` despite their Index status in the installed dictionary; the runner did not pin the frozen contract, accepted G01.var05 sign-off and closure, manual, or dictionary; and calc did not require zero converter errors. These defects were corrected before the final preflight.

The corrected builder reproduces `native-input.json` SHA-256 `7e990242656119f9424fcf390ae8c46eb23e4751dbe6fb44bd80b3bb4cf307d1` from accepted G01.var05 input SHA-256 `ef21268a1f4c024e0c5bea24136509446e356ea3214dedd694c67825f376f984`. The only changed tables are `ProblemDescription`, `Control` (`RELOP=REDUNDANCY`), and the added `Redundancy` row. Its indexed `RLID` and `SID` columns now have `key: true`; the row uses `TEACH-LRU-01`, `TEACH-AIR-01`, `NRL=2`, `NRLRQ=1`, `ACPA=ACTIVE`, and `TSWOV=0`. The parent has two installed LRUs, and the child has 22 populated tables.

Current frozen hashes: contract `136a61bd7eedf9215a8015e986db473ed10be7b5403f36278edf339861d045fb`; builder `327378c291f759a2c72af1be87da3612ba6eb2d08b4b70effbf848c3f79effa6`; checker `dfa8f11b93763bc59707a0f0543b8336d77e27baf7b2d62676115cec8a3340f7`; runner `dcfeb3b52591e45948bdef3d84cfa1c5887889695930b3b7d21e8801d6c3d322`. The runner pins the accepted G01.var05 sign-off `c2555954391a93ae062b1bb094fad72f16db783e1752309f7d8cd3163021ede7` and closure `1918f5573953952dae76a5f35631e5c96070b60f5347f914f912f0dca57148c9`, plus installed manual and dictionary fingerprints.

Builder verification, Python AST and PowerShell AST passed. The runner requires session-0 SSH with an `sshd.exe` ancestor, an idle host mutex, and active GUI PID 13340; it uses hidden CLI processes, restores the Prelife Log registry option, records pre/post source and raw hashes, requires conversion `Errors=0`, one warning `#108`, `Notes=0`, and runs the import/export checker. The warning gate matches the code, not its form or full text; the native log should be reviewed before any acceptance claim.

The native run must establish whether this fixed-seed 1-of-2 ACTIVE single-item link behaves as hypothesized. In particular, a two-link-failed transition cannot be claimed unless observed. Series links, PASSIVE switching, nonzero switchover, broader quantity thresholds, GUI behavior, and stochastic generality remain outside this preflight.
