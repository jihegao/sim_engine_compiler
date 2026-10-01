# J02.var02 integer rectangular count: bounded CLI signoff

**Decision:** `native_behavior_accepted_cli_scope` for 32 fixed-seed,
one-repetition native runs of the A03-derived two-aircraft formation.
Reusable publication requires merge to `simlox/main`. This does not
complete J02 or Issue #18.

The accepted `A03@1.0.1` parent input SHA-256 is
`d7aa35c11a1426de1e74167cc6a3277879f4a2a5814792274490a43dcfe986a4`.
The frozen [panel diff](panel-diff.json) SHA-256 is
`20f452283da051c3c4009428363b3a9b00fe347e260e3b11c6bf332bb56415f9`.
Seed 01 changes `OperationProfile.ITYPE` from `SCHEDULED` to `RANDOM`,
sets `IQTYD=COUNT03` and `IDISP=EQUIDIST`, adds an
`IntegerDistributions` row with `PFAC=1`, `<IRECT>`, lower 0 and upper
3, and changes `SystemDeployment.QTYPS` from two to six. `IPER=0`
keeps all generated missions at hour 8. The mission still requires two
aircraft for two hours. `IQTY=1` remains but native warning #211 says
it is ignored under user-defined `IQTYD`. Seeds 02–32 differ from seed
01 only in `Control.RSEED`; all retain `NREPS=1`.

The installed database dictionary SHA-256 is
`11a61537c95489e32742d98ca8532b42aa1ec728c270009e5b1a8643325e96d0`;
manual SHA-256 is
`39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`.
Manual pp. 271–274 and 541–543 describe random initiation, zero
period and integer distributions. The installed dictionary permits
`<IRECT>` with nonnegative parameters. Native import/export accepted
and retained the row in all 32 runs.

All 32 [indexed](evidence-index.json) runs used guarded session-0 SSH,
the host-wide Issue #18 mutex, and preserved GUI PID 13340/session 1/start
identity. Import, export, calculation and JSON report completed with
zero converter errors and classified warnings #108/#126/#211. All
populated source tables roundtripped exactly. Every positive realized
count starts that many successful two-aircraft missions at hour 8,
ending at hour 10; the two aircraft in each formation are distinct.
The zero-count runs have no activated or started mission, zero flight
hours and six ready aircraft throughout, despite an unactivated
profile sentinel in the event log. Every run has 72 System and Stock
half-hour bins, four aircraft flight hours per realized mission, no
stock demand and six ready aircraft at the horizon.

The 32 observed counts have frequencies 0:8, 1:7, 2:9 and 3:8;
sample mean is 1.53125 and sample variance is 1.289314516. Zero-count
seeds are 02/09/16/18/23/25/30/32; count-three seeds are
05/07/12/14/19/21/26/28. The
[author panel replay](review/author-panel-validation-2026-10-01.json)
passed with 352 sealed raw artifacts. Independent read-only review is
recorded in the [verdict](review/independent-readonly-2026-10-01.json):
45,408 checks passed with zero failures across the 32 accepted runs
and all 352 raw seals. Independent script SHA-256 is
`9f93eb8b89edb6a2097507472f86a94aa6cf670b199f84c3a04737474cd6d8f6`;
verdict SHA-256 is
`ed195264c21af9d477f8ff21bb7662ced4b7be9c6b3b5d2148fa7ce059c44600`.
The 32 earlier `-probe-` runs
are diagnostic and excluded. Raw native artifacts stay in ignored
`runs/` paths; the evidence index publishes accepted run IDs and raw
SHA-256 seals.

This panel documents fixed-seed native observations. It does not prove
population probabilities, endpoint weights, independence, other count
ranges, capacity-shortage behavior, GUI-only behavior or cross-engine
parity. J02.var01, var03 and var04 remain separately scoped.
