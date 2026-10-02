# I01.var03 bounded CLI signoff — maintenance station selection

Status: accepted for the precise positive station-selection scope below, subject to exact-head PR CI and merge. Issue #18 remains open.

## Frozen sources and controls

- Direct accepted parent: I01.var01 stocked input SHA-256 `9e88c4bb95e1ca1ad4ec255c0fb9996fcbab8cd80b61972771574eb416233bfb`.
- Accepted structural donor: E04 FAST input SHA-256 `2791e5ab4d0ddeccc869bcb173320039ea4f524463881d03fbb466c0b68fbba1`, supplying DEPOT-01 WS and BASE→DEPOT two-hour FAST support.
- Base input `4e16325638ff7aafcf47306101b42a780c02b06f957c0036317e300eb63abf72`; depot input `0c153ced2f53729b526dc8cad76808f5270365cc7cbe71a90a90c0bbf902d770`; exact diff `f0fa976d5c8a612c0c6ff59206740016d829ea42b54b622e80ce1b93e2310ff7`.
- Pre-run contract SHA-256 `26fef4eb944e749d5cf15a591addd0dd9db5348610d8b5b4660bc187f3cdf9b6`. The paired source changes only `Control.APID` and ProblemDescription. Both APIDs carry equal base spare1/depot spare0, complete `LRU-CM/BASE` maintenance allocation, and the same one-hour task-referenced LRU repair at both stations.
- Installed SIMLOX executable, manual and table dictionary fingerprints are pinned in the contract. The installed manual physical pp. 338–339 and 439–441 defines matching task category, level and station; the native run tests the implemented behavior.

## Native and independent evidence

- Two fresh serial guarded session-0 SSH runs: `i01-var03-station-base-v100-ssh-20261002-01` and `i01-var03-station-depot-v100-ssh-20261002-01`. Both preserve GUI PID13340 and the host-wide mutex, have source-stable closure with no error, exact 24 populated authored-table import/export roundtrips, zero converter errors, valid SXO/report, and 12 SHA-256 sealed local raw files each. Raw files remain ignored locally.
- Common physical failed LRU ID1 at h9.8829 aborts the first mission; base spare ID0 is drawn h10 and the aircraft is ready h10.5. The base arm repairs ID1 at BASE h10.1667–11.1667 and restores base stock1. The depot arm transports ID1 BASE→DEPOT h10.1667–12.1667, repairs at DEPOT h12.1667–13.1667, transports back h13.1667–15.1667 and restores base stock1. Later missions succeed at h22 and h34; terminal ready aircraft count is one. Both 72-bin System/Stock reports and summary agree, while the physical log proves the repair-station and stock-timing contrast.
- Author replay: 25/25 checks, SHA-256 `22069b420ba4efbf798d16e20ec3e8321cbfdb9142db18e8910c9a1f22cd4ba3`. Separate reviewer replay: 2,016/2,016 checks, verdict `GO_BOUNDED_MAINTENANCE_STATION_APID_SELECTION`, checker SHA-256 `aad3f9ce1926cf17fc08d9678bd3aeabb7a96de4c28e65aba45a2d7f67bffa9a`, verdict SHA-256 `dfc1bdd70c1ed2dac723fb1cd3b5e4d5275b4c39a21de82c29bc907a4c7b6870`.

## Scope and limits

This accepts `Control.APID` selection of the task-referenced repair station for one `LRU-CM/BASE` LRU with both POINTs complete. Transport and stock timing are downstream coupled observations. This does not accept positive category or level filtering, simultaneous stock/resource/maintenance POINT selection, `<NONE>` reorder, generic station routing, GUI visual behavior, or cross-engine parity.
