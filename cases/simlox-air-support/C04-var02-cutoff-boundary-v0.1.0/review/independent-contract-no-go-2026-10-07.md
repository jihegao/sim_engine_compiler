# C04.var02 contract review — NO_GO_CONTRACT

Reviewed contract SHA256 `9f30694d4046b0d15cdfd72f89563e9f159980130d8055825bd3ce6893b3c555` (30,292 bytes). This is a read-only contract review; no native or GUI process was invoked.

## Verified evidence

- All 25 accepted C04 source records match both disk and `HEAD` Git blob byte sizes and SHA256 values. The accepted contract, evidence report, and independent review match their pins. The installed manual matches 18,124,110 bytes and SHA256 `39427027c46809a9ce9ebcb9be04e7396d96746e42a6f8c7c0ba2ddc294ef8a3`.
- The three final `-02` C04 runs match their input, parent-diff, closure, invocation, model-log, and report pins. All 33 raw files match the declared sizes and SHA256 values. The direct C03 staffing-1 contract, evidence, review, input, closure, invocation, and 11 raw files also match. The excluded horizon-wait run log matches its pin and its SXO is four bytes.
- The three 31-table inputs each contain 201 authored row cells and 979 scalar JSON leaves. C03 staffing-1 to each child, and every pair of children, differs only in `OperationProfile.DTIM`: `1.0` to `0.51`, `0.50`, or `0.49`. Their declared latest launch times are h8.51, h8.50, and h8.49.
- Before and equal have byte-identical full model logs and reports. Each report has six tables totaling 5,210 cells. Against before, after differs by table in exactly `0/4/15/0/1/1` cells. The after log cancels at h8.49, stops the second aircraft's active preparation, frees P-CREW, records factor `0.98`, and returns both physical aircraft ready. These observations support the narrow three-arm question; they do not establish a general same-time ordering rule.

## Blocking wording defect

The third predeclared acceptance bullet requires the “original responsive session1 GUI PID13340/start timestamp preserved after each of four import/export/calc/report steps.” The accepted runner verifies session 1 and responsiveness at preflight, but after each step it checks only process count, PID, and start timestamp. Its `steps.json` records only `coexisting_gui_present_after` for GUI preservation. Thus the frozen raw evidence cannot prove continued responsiveness or session identity after each individual step. The contract should require **responsive session-1 GUI at preflight and the same PID/start timestamp present after each step**, matching the historical evidence. A revised immutable contract can preserve all other gates and be reviewed separately.

The partial cleanup is collateral to the cutoff comparison and should remain bounded to this one fixed model; C04.var03 retains its separate classification. No child simulation or publication is approved by this memo.
