# I05.var05 scheduled item replacement — v1.0.7 source candidate

Status: distinct source candidate; no v1.0.7 preflight or native action has occurred. The accepted H02.var04 parent input, evidence index and 12 original raw files remain read-only and are not rerun.

The child behavior remains one hour-5 `ChangesItemReplacement` row for `TEACH-AIR-01 / TEACH-LRU-01 / BASE-01`, changing `SURPT` from 1.0 to 1.5 hours. The child input remains byte-identical to v1.0.4/v1.0.5. v1.0.4 is a preserved native `NO_GO` after import/export and strict roundtrip checker exit 1; calculation and reporting did not start. v1.0.5 is a preserved `NO_GO_SOURCE_ONLY` because its reviewers found precision-token, huge-integer, mixed-instance placeholder, and missing-manifest-file issues. Neither result is accepted or retried.

v1.0.7 prospectively defines the finite serialization rule: exact 36-table order, columns and instance names; 25 authored populated tables; an all-null placeholder only for a wholly empty table; exact Decimal numeric equality or the exact 17-significant-digit spelling of the authored finite binary64 value in declared `double` columns; all other cell types and values exact. JSON decimal tokens are parsed as Decimal before comparison. No tolerance is allowed: authored 1.5 rejects output 1.50000000000000001. Private negatives cover sub-ULP changes, huge integers, booleans, partial-empty instances, malformed/extra rows, optional null changes, non-double edits and table order.

Run ID: `i05-var05-item-replacement-v107-ssh-20261009-01`; native path is unique and must be absent. A new independent source review, local gates, PS5 SSH preflight and separate receipt-bound `GO_PRELAUNCH` are required before one native attempt.

No immediate replacement task at hour 5 is expected. Later task duration, item identities, repair, stock and report ledgers must be reconciled from raw evidence. No stochastic time shift, other schedule field, GUI behavior or general I05 rule is inferred.


v1.0.6 is preserved as NO_GO_SOURCE_ONLY because its source freeze omitted the authoritative publication index. v1.0.7 pins and validates the exact H02.var04 parent publication entry in both source freeze and prelaunch manifest.
