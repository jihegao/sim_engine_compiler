# B01.var03 task-route arm: explicit mission type

This candidate uses the accepted [B03 1.0.2](../B03-explicit-cold-hot-v1.0.2/README.md) source and its sealed native run as the parent. It changes exactly the 08:00 `OperationProfile.SPRID` from `COLD-FIRST` to `HOT-SORTIE`. Both recipes already exist in the parent. The [contract](contract.json) predeclares the event and complete report comparison; it is pending independent review and native verification.

Run `build.py --check` to verify the one-cell source delta. The frozen source is not evidence of native behavior. B01.var03's aircraft and site mapping arms are outside this version.
