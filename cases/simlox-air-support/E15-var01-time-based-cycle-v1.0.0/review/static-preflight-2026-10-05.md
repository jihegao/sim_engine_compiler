# E15.var01 independent static preflight

**NO-GO pending one converter-warning gate correction.** No native
process was launched; the intended run directory was absent.

The current runner SHA-256 is
`55b5b6e3a94b4b389ec7d7502ec2011d8d31a7ac3f19b965554cb43c7cb58765`;
PowerShell parsing reports zero AST errors. The contract SHA-256 is
`e5ba51841c45e9ca099d1f063e6c6b48234af01638121bd18b538a8fe9e81965`.
All 14 literal contract/input/builder/checker, E02 and accepted E15
parent/source/report, selector/settings, executable and manual pins match
their local files. Both Python sources parse. An independent JSON diff
shows 31 tables, 21 populated, and exactly one changed model cell:
`ItemReorder` row `[TEACH-DU-01, DEPOT-01]` has `ROINT` null→16.0.

Installed manual physical pages 343, 345 and 447 say a positive ROINT
selects scheduled time-based reorder, with variable order quantity, and
that ROSIZ is ignored with a warning. Omitted ISTOH is compatible with
the time-based minimum when the opening level equals STSIZ4. The exact
first cycle, order and receipt remain native hypotheses.

The runner requires a unique fixed run ID, session-0 SSH with an
`sshd.exe` ancestor, nonblocking global native mutex, active protected
GUI PID 13340/session 1/start identity, hidden target-only watchdog,
and source hashes before and after. It checks 21 authored populated
tables by native import/export before calculation and seals an immutable
raw closure, including failed or partial outcomes. A selected report is
attempted only after converter and SXO/log gates.

The warning gate is weaker than the frozen contract. It requires
Errors 0, Warnings 2, Notes 0, first warning #108, and **some** warning
line containing `ROSIZ` and `ignor`. It does not require that the second
warning identify the sole target ItemReorder row, item or station. A
generic or wrong-row ROSIZ warning could therefore pass and allow the
report step despite the contract's row-specific requirement. Tighten
the gate to the target table/record and item/station fields supported by
the actual native warning format, or narrow the predeclared claim before
launch. Re-pin the contract/runner if modified, then recheck syntax and
fingerprints.
