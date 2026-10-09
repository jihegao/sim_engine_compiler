# I05.var05 v1.0.8 replay-only candidate

This version changes the native behavior validator to match only complete top-level `system SURP task … started/completed` event lines. The v1.0.7 validator also matched nested remove/fit subtask lines, causing a duplicate task ID error.

This candidate replays the immutable v1.0.7 native output. It does not create a new SIMLOX run, change the native input, or accept the v1.0.7 original runner failure. The source run remains a sealed `NO_GO`; acceptance requires independent review of the corrected validator and its replay result.

Source run: `i05-var05-item-replacement-v107-ssh-20261009-01`.
Input SHA-256: `c30b0849ad46a6351e4c94a2964f0f6f16274b6b926508b8fe47ecd9a5323480`.
Failure seal SHA-256: `90ab30ca55d18d1432a9b4f5ae0aab8d15375361c6855c4231ff2224bed9e7a0`.
