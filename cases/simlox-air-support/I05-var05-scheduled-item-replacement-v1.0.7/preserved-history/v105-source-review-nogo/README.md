# I05.var05 scheduled item replacement — v1.0.5 source candidate

Status: a distinct source candidate after v1.0.4 failed its frozen roundtrip gate. No v1.0.5 preflight or native action has occurred. The accepted H02.var04 parent is retained read-only and will not be rerun.

The child change remains one hour-5 `ChangesItemReplacement` row for `TEACH-AIR-01 / TEACH-LRU-01 / BASE-01`, changing `SURPT` from 1.0 to 1.5 hours. Its source input is byte-identical to v1.0.4. The only changed acceptance scope is a prospective, finite converter-serialization policy derived from the sealed v1.0.4 import/export failure: 36 table names/order, exact columns and instance names; 25 authored populated tables; one full-width all-null row allowed only for a source-empty table; and exact finite numeric equality across JSON integer/float encoding only for columns whose metadata says `double`. All other values and types stay exact. No tolerance or rounding is allowed.

v1.0.4 is preserved as `NO_GO`: import/export completed, the frozen checker exited 1, and calculation/reporting did not start. Its failure seal and independent A09/A17 read-only reviews are retained under `preserved-history/v104-roundtrip-failure/`; the original raw files remain in the unique v1.0.4 directory. This outcome is not retroactively accepted.

The v1.0.5 child has unique run ID `i05-var05-item-replacement-v105-ssh-20261009-01` and a distinct absent native directory. It requires fresh independent source review, local gate receipts, SSH PowerShell 5 preflight, and a separate receipt-bound `GO_PRELAUNCH` before one native attempt. Any failed attempt remains sealed and is not retried in place.

The business behavior and limits remain unchanged: no immediate replacement activity at hour 5; later replacement tasks use the changed duration if their native event records support the relation; physical item, repair, stock, and report ledgers must reconcile from raw evidence. No stochastic shift, other schedule field, active-task behavior, GUI behavior, or general I05 rule is inferred.
