# Author construction notes before source freeze

The first mutable report oracle counted both aircraft as `NSYMP` throughout each one-hour preparation, producing a four-aircraft-hour integral. The frozen contract requires three: after the first aircraft finishes its half-hour task, its remaining half-hour before launch is `NSYMR`. I corrected this source-state classification and the synthetic 5,210-cell oracle now satisfies all seven declared integrals. The first draft bytes and failing command output were not saved as files, so no original draft SHA is claimed.

The first mutable roundtrip comparison used JSON representation equality for populated rows. The accepted parent export writes declared double cells such as `36.0` as JSON integer `36`. The checker now compares finite numeric values for declared double columns while retaining recursive type-exact column and instance metadata and rejecting booleans. This was a read-only accepted-parent calibration; no parent source or raw bytes changed.

The initial copied PowerShell receipt templates had read-only file attributes inherited from the accepted source. One attempted edit failed without changing their bytes. I made only the new working copies writable and adapted their schema and probes. The original accepted helper and receipts remain unchanged.

These are author development corrections before the final manifest or any SSH/native run. Synthetic positive fixtures exercise parser and oracle code paths; they are not accepted native behavior.
