# E11.var04 and E11.var05 transport-direction label correction

The installed SIMLOX 2017 manual, physical pp. 317–318, defines `TFRMS` as the time to transport an item **down from the mother station to the supported station**. It defines `TTOMS` as the time to transport a faulty item **up to the mother station**. The installed manual SHA-256 is `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`.

| Published case | Frozen numeric input | Correct direction | Incorrect frozen prose |
| --- | --- | --- | --- |
| [E11.var04](../E11-var04-nonzero-ordinary-times-v1.0.0/cli-scope-signoff-2026-10-03.md) | `StationStructure.TFRMS=7`, `TTOMS=11` hours | **7 down** to BASE-01; **11 up** to DEPOT-01 | `ProblemDescription.PDESC` in the frozen input and exact diff says “7h up/11h down.” |
| [E11.var05](../E11-var05-item-route-ignored-v1.0.0/cli-scope-signoff-2026-10-03.md) | `ItemStationStructure.TFRMS=5`, `TTOMS=7` hours | **5 down** to BASE-01; **7 up** to DEPOT-01 | Frozen `PDESC` says “5h from/7h to”; the pre-run contract's interpretation and `item_specific_from_base_hours` / `item_specific_to_base_hours` keys reverse the direction labels; the original README repeats the error. |

The original descriptions, pre-run contracts, exact diffs, native inputs, raw artifacts and evidence indexes remain unchanged to preserve their pre-run and publication SHA-256 seals. This document corrects **labels only**. The intended field values and native observations are unaffected: E11.var04 converter warnings #2076/#2077 say both ordinary station-link times are ignored for autonomous BASE-01; E11.var05 warning #445 says its added item-specific row is ignored. Each child's complete event log and every non-description report row match the accepted E11 base. Both physical transports start and arrive at h11 with zero logged travel time in these bounded runs.

When deriving a new model, use the manual's field directions above. Treat the reversed words in the frozen descriptions and contract metadata as historical text, not modeling guidance. This correction does not extend the cases to other stations, items, policies, or engines.
