# E15.var10 independent post-run static review

**NO-GO for the frozen negative contract; preserve as an excluded
diagnostic.** The runner did not misclassify the converter output. The
predeclared gate required an explicit converter error and no valid
simulation output; neither condition occurred.

The immutable run
`e15-var10-rosiz-over-limit-v100-ssh-20261005-01` has closure SHA-256
`b05c79aeaef20c4c4faf72a4ea2a6726f6806a61c7096523f3069140d34e7591`.
I independently matched all 11 raw file sizes and SHA-256 values against
that closure, its invocation hash, and all 12 current source hashes against
both the before and after maps. The source and runner bytes remain pinned.
The invocation records session-0 SSH with an `sshd.exe` ancestor, the
global native mutex, and protected GUI PID 13340/session 1/start identity.
All three hidden import, export and calculation steps exited zero and
recorded preserved GUI identity. The 21 authored populated tables passed
the import/export checker; its 31 native populated tables include native
placeholders.

The calculation log identifies `StockAllocation` record 2 and says
`(warning #168) Reorder size too large (ROSIZ > STSIZ+1): TEACH-DU-01`.
It also has expected warning #108. The converter summary is Errors 0,
Warnings 2, Notes 0. Calculation completed and wrote a 358,607-byte SXO
and a nonempty model log. The runner consequently recorded
`expected_negative=false` and `expected converter error absent`, with
no report step. The installed manual's stated bound still explains the
warning; this one CLI run does not show converter rejection.

The next defensible slice would preserve this run unchanged and freeze a
new, separately reviewed contract for the observed warning and valid
calculation. A guarded report-only extension from this exact sealed SXO
could test any output claim. No positive ROSIZ-over-limit simulation
behavior or broad E15.var10 conclusion is accepted from this diagnostic.
