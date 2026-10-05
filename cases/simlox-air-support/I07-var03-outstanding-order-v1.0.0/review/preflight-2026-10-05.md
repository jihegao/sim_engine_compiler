# I07.var03 pre-run review

The first draft runner (SHA-256
`fcf8c106c0136ce0b93fbd613bf7d1c490c27830ecc1897b7d62ed9ddaa08e73`)
received **NO-GO before native execution**: it accepted warning patterns broader
than the frozen contract and deferred exact roundtrip until later replay.
No run directory was created. The source and comparator pins were otherwise
valid. The earlier contract pin was
`448e6c2d557ff90b7f3ac72ca786355ddd1f11ef6808b7b282b74d7f88b2e0eb`.

The corrected contract SHA-256 is
`e511d3ce02d03b594517a0eaeec4d9906a7d06be907e6eba4f9c4ef3ea5dd8c3`;
runner SHA-256 is
`48be491e95dd99a03e0cdf92d319dff87f97aa1c3ea8842ff757b98932d19943`.
The runner pins `check_roundtrip.py` SHA-256
`7c723805efb33fb96031a07f9d14f4fafa732a30ee0c319c9d18bdd67354d3a9`
and runs it after native export and before calculation. It now requires
Errors0/Warnings1 (#108 only)/Notes0. The accepted E15 comparator input and
signoff are also pinned in the runner's before/after source map.

An independent contract reviewer gave **GO for one guarded run** after
checking the installed manual p497, eight-column dictionary schema, exact
TIMEC5→10.5 delta, accepted I07.var01 h5 comparator and E15 original-order
comparator. An independent static reviewer gave **GO** after rechecking
PowerShell syntax, source pins, unused run ID, session-0 SSH, sshd ancestry,
global mutex, GUI PID13340, hidden targeted watchdog, pre-calc roundtrip,
strict converter gate, and raw closure. Neither reviewer invoked native code.

The old-order claim is limited to one pending order. The native log need not
print an h10.5 change application, and no later order is induced here.
