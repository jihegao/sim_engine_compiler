# A14.var06 repeated profile v1.0.0 diagnostic

**Decision: NO-GO for the frozen full-horizon acceptance.** This package is retained as a reproducible native diagnostic and is absent from the publication index. The corrected [v1.0.1 package](../A14-profile-repeated-v1.0.1/README.md) has a separate pre-run contract and fresh run IDs.

The [contract](contract.json) compares a no-dependency control, two explicit `MissionDependence` rows and one `MissionDependenceProfile` row over two hierarchical waves at hours 8 and 32. It derives from accepted A14.var01 input SHA-256 f81445ad2daba09321e7a55ad67c5355b7e4a14ec3a58bbf10fbfcd18b343376 and accepted A09 profile input SHA-256 e795c5fcf563f8e42ab9e9cb161a925bec3b06157cbbecde7901e99bfec91d85. The [exact diff](exact-diff.json) SHA-256 is 1111663f96542d3fb1b8e8ba23ac30b52377bf01370391ed6d8e33a364eb1c75.

| Variant | Native run ID | Closure SHA-256 | Event-log SHA-256 | Raw report SHA-256 |
| --- | --- | --- | --- | --- |
| Control | a14-profile-control-v100-20261001-01 | 5cd847d663bade60f4d57d84bf0d98e24eb460b3150c311ac4bdf8fe691324a2 | 71bc0778e716941bd118928021a1b51081911997fdf552ed43cb1c58146b6d03 | 2d90c7c7737247fac98a7f7ca1cfcdc97a169d27d05a95449ba459b1ea07ff11 |
| Explicit | a14-profile-explicit-v100-20261001-01 | c893dc6cbe7ba94c07f8a6ec8c3618994ff07e6da1f193e02ea3bc96b117b3be | e45b2e34cb6ba32744bf2b921cbb94767c9158ade7d6a4c9f1f0bdbe4cd8331c | b2ae0138fb8307bac71d78671669d230b622a51da97bd1f76eb1eb9a37abebe1 |
| Profile | a14-profile-profile-v100-20261001-01 | a42264f89cb3cc82e7cba1057db295df33bbf5d75a6b079cf05bfaf06ba5f001 | e45b2e34cb6ba32744bf2b921cbb94767c9158ade7d6a4c9f1f0bdbe4cd8331c | 8648058accf7206086f36eed7100fee314da40aef5172a63cfeb834a6c074854 |

All three guarded session-0 SSH runs passed import, export, calculation, report and source-row roundtrip; conversion errors were zero, and GUI PID 13340 remained intact. Event logs contain two waves, and explicit/profile logs are byte-identical. The source inherited explicit MISSION and SYSTEM `ResultCollection.RCEND=16`, despite `Control.RCEND=40`. Consequently native SystemResults has only **32** half-hour bins ending at 16, whereas StockTotalResults has **80** bins ending at 40. The frozen contract required both to span 40 hours. The invocation copied runner metadata `case_version=1.0.1-candidate` despite this directory's `1.0.0-candidate` contract; this provenance mismatch is also a NO-GO finding.

An [independent read-only verifier](review/independent_readonly.py) SHA-256 d29d520fe738fa7669abf3a6caeeba24cd39e4fcdc6b7ca7aee622d1d729e315 reports [7,853/7,865 checks and 12 failures](review/independent-readonly-2026-10-01.json), report SHA-256 5156486dacca7febbce6b20e6dd076a99ecc024452dec45eae0a88907d445748. Its passing event comparisons do not convert this package into an accepted case. Bulky raw outputs remain in ignored local `runs/` paths, indexed by the immutable closure hashes above.
