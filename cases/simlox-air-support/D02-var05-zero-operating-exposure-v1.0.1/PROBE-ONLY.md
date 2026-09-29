# D02.var05 second no-profile probe: default mission counterexample

This candidate removed both the three `OperationProfile` rows and the now dangling unit `Operations` assignment from accepted D02.var01. Native conversion succeeded in sealed local run `d02-var05-zero-op-v101-ssh-20260930-01`, but generated a default mission spanning the entire 60-hour horizon. That mission started at hour 0 and a traditional critical failure occurred at 1.8829 hours. Closure SHA-256: `35800c4d3d1ce8dc82ad961f36e6358266c97a486a4988c12b5ca0fa79cc66ac`. This is **not a zero-exposure control** and is not published as D02.var05; the raw run is retained under ignored `runs/`.

The corrected experiment and its accepted scope are in [D02.var05 v1.0.2](../D02-var05-zero-operating-exposure-v1.0.2/README.md).
