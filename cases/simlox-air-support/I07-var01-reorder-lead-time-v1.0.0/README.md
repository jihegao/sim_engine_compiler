# I07.var01 — scheduled depot reorder lead time

This bounded pair derives from accepted E15.var07 explicit-three depot stock. Both arms start with three `TEACH-DU-01` units at `DEPOT-01`, a stock target of four, a reorder size of two, and an existing one-hour `ItemReorder.LEADT`. Control has an all-null `ChangesItemReorder` placeholder; change sets that existing record's lead time to three hours at h5.

The same h10 demand lowers depot on-hand from three to two and starts one two-unit reorder in both arms. The order arrives at h11 in control and h13 with the change. Selected `ItemResults` half-hour bins retain on-hand two until the respective arrival and four thereafter. The first mission aborts following the original E15 component failure; the later h20 and h32 missions succeed in both arms. This demonstrates use of the scheduled lead-time value for a later stock-based order. It does not exercise an already-outstanding order.

`build.py` verifies and recreates byte-pinned inputs. `run_native_ssh.ps1` completed eight guarded session-0 CLI steps. `validate.py` and the independent reviewer replay check source pins, exact row-containing-table roundtrips, native events, selected reports and local raw seals. The SXI/SXO/log/report bytes remain in ignored local `runs/` and are pinned in `evidence-index.json`. The E15 report selector is reused by byte pin to select the depot's item results.

Scope: one fixed seed, one existing depot reorder, one h5 `LEADT` update and one later h10 order. `LEADTD`, interval policy, outstanding orders, tie-time changes, other `Changes` tables, GUI, cross-engine behavior and general I07 remain untested.
