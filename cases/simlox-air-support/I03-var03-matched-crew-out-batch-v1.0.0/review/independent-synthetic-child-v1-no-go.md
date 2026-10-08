# PURE child fixture review: NO_GO

The author's `synthetic-child_out2.log` is a prelaunch PURE fixture (16,569 bytes; SHA-256 `9b465dca9ef1cff6f96e63a480f9e0d66a92563c7d8875fc599710515c593401`), not native evidence. Independent mutable reader `independent_replay.py` (25,167 bytes; SHA-256 `ee0bb1d33d1a7e87e8c2547190d2a9041d7eab7b59e957a7f343d8010ad91316` at probe time) rejects its h8 second maintenance release, line 86, which prints P-CREW `available now: 2`.

The fixture has opening3, two booked at h7.5 and a positive OUT1 at h7.75, leaving no free crew. At h8 first release makes one available; the pending OUT backorder is removed and its next task created before the second release. Accepted I03.var01 `out.log` has the same ordering and its second h8 release prints `available now: 1`, reflecting reservation of the first freed crew for OUT. The child fixture's second release must therefore print 1 under this task-linked conservation. Its printed 2 would account for the same reserved crew as still free. This is a fixture discrepancy; it says nothing about a future actual child run.

Preserve the old fixture bytes and make the production ledger reject this quantity. Revise a distinct synthetic fixture only after deriving the reservation timing from the accepted native trace. No SIMLOX call, source model change, or acceptance gate was made by this review.
