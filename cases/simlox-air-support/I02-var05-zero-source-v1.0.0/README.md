# I02.var05 — zero source stock at the scheduled transfer

This matched pair tests the zero-stock arm of I02.var05. It derives from
accepted I02.var03. The frozen control moves the one-unit BETWEEN schedule
from h6 to h2, before the unchanged h4 IN. The child changes only the
depot's initial `StockAllocation.STSIZ` from one to zero and the description.
Each delta leaves 30 other tables unchanged. Both arms retain `TFQTY=1`,
`TFDT=0`, item tracking, half-hour result collection, seed and 36h horizon.

Two serial guarded session-0 native runs preserve GUI PID 13340, convert
with zero errors and round-trip all 22 populated authored tables. Control
depot item ID 0 moves to base at h2. The zero-stock child begins the h2
BETWEEN with zero items and adds one transfer backorder; the task arrives
with zero physical items. Its h4 IN item ID 0 removes that backorder and a
second BETWEEN moves the item to base at h4. This paired contrast isolates
source availability at the scheduled request.

Four report-only exports from the two sealed SXOs show native `ItemResults`
for depot and base, 72 half-hour bins per arm and station. In both arms,
base nominal `STSZ` rises from zero to one at h2. Control base `STOHA`
rises at h2; zero-child base `STOHA` remains zero until h4. Child depot
`STSZ` and `STOHA` remain zero throughout. A later ordinary depot backorder
starts at h10 in the child, clears at h13.1667 when failed item ID 1 is
repaired, and base receives that item at h15.1667. Child terminal depot
stock is zero, base nominal and on-hand are one, and depot `NBO` is zero.
The control follows its separate one-unit depot stock and h12 replenishment
route. System, aggregate stock and mission report tables match between arms;
station item tables and horizon averages differ.

The target's nominal `STSZ=1` at h2 in the child coexists with zero on-hand
and an open transfer backorder. This is a native observation, not evidence
that a physical item moved at h2 or a general nominal timing law.

`build.py`, `describe_diff.py` and `validate.py` reproduce and replay the
case. `make_report_settings.py` recreates proprietary station selectors
from a pinned installed default. Native raw files and selectors remain
local and ignored by Git; `evidence-index.json` seals their SHA-256 hashes.

This covers one zero-source h2 request before h4 IN versus one matched
available-source control. Other quantities, standalone zero-stock transfer,
general priority, reorder/procurement, positive delay, GUI visuals and
cross-engine parity remain unverified.
