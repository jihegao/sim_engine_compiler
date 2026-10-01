# G01.var05: two interchangeable installed LRUs

This fixed-seed native CLI case derives from accepted [G01.var01](../G01-var01-lru-sru-v1.0.1/cli-scope-signoff-2026-10-01.md). The [contract](contract.json) and [native input](native-input.json) were frozen before the guarded run. The [exact diff](exact-diff.json), [signoff](cli-scope-signoff-2026-10-01.md), and [evidence index](evidence-index.json) define the bounded acceptance.

Run `build.py` to check the frozen source against its parent, `describe_diff.py` to check the four-table delta, and `validate_native.py runs/g01-var05-qty-v100-ssh-20261001-01` to replay author checks. The independent checker is under `review/`. Raw SXI/SXO, event log, report, invocation and closure are retained locally under ignored `runs/g01-var05-qty-v100-ssh-20261001-01/`.

This case sets `ItemStructure.QTYPM=2` for one LRU type. It also sets system `FRT=600000` to cover two child rates of 300000, and gives local LRU stock two spares. It preserves the G01.var01 SRU and repair route, missions, seed, and horizon. Distinct failed LRU physical identities 3 and 5 appear at the aircraft, each replaced from stock by a different spare. Their initial mounting is inferred from the stock and replacement identities; the log has no time-zero mounted-item roster. The paired `NSIMI` contrast and other seeds remain separate work.
