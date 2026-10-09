# Preserved v1.0.2 README review failures

Independent reviewer `a17_static_reviewer` returned two NO_GO findings before the final source-freeze correction.

1. The earlier README incorrectly identified the v1.0.2 package as a v1.0.1 source candidate and mentioned only the v1.0.0 preflight failure. Its preserved-history directory already contained separate v1.0.0 and v1.0.1 preflight failure seals. That README was preserved byte-for-byte as `v102-readme-nogo.md`, then corrected to identify v1.0.2 and both failures, each with zero native dispatch.
2. The corrected README initially stated that `source-freeze.json` pinned it while the freeze still carried the prior README hash. The freeze and its verification were reissued. Current `README.md` is 3,549 bytes/SHA-256 `347aa7ea8ce5c83ca20b238a537173b3fa573d29e1a1e96e9bb4992afe340391`; current `source-freeze.json` pins that exact size and hash. The current freeze SHA-256 is `414f60494186fbc240130f0af5fba3685797db7ad3303882f7e7204abc6e6526`.

These were documentation/freeze-review findings only. No checker, SSH, native, converter, simulation, or report action was performed for either NO_GO.
