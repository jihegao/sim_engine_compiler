# I07.var02 ROSIZ pre-run review

The v1.0.1 source was frozen before any native call. The contract SHA-256 was
`7fdb7ac423e8921f22acb30ba0b675cfa271cb36740b43f6f28b6034da09ec30`;
the runner SHA-256 was
`d52de5fc5ec06cafd33935fa001da085b8f99144d835518dd690e8fd5f60b0b8`.
The builder, control input and change input were respectively
`3077c78ddc0cc524e6426c584325afbc10ecd146cbd5ac0df53816c2c2ae971b`,
`c6aa9ee1f86204dba3922765a29fa5225547710827db144b6abcacf106eaf84e`,
and `b179428b3f72158bf9d32ce2675cc107fbadc60c6c3597bbab92abf24f70b2c2`.

The independent contract reviewer gave **GO for a guarded native test**. They
checked the accepted E15 default stock parent and signoff, installed manual,
dictionary, executable, selector, and exact pair diff. The only paired change
is `ChangesStockAllocation` at h5, setting ROSIZ to one at the existing depot
point. Both arms have nominal and opening stock four. At h10 a shared demand
should leave control above its reorder point two and child at its point three.
The precise order size remained a falsifiable native observation.

An independent static runner reviewer gave **GO for a guarded diagnostic
launch**. They checked the PowerShell syntax, frozen pins, unused run ID,
session-0 SSH and sshd ancestry checks, nonblocking global mutex, protected
GUI PID 13340, hidden children with targeted watchdog, serial stages and raw
closure. They required post-run validation of exact populated-table roundtrip
and precise inherited converter warning count because those are not enforced
fully by the runner.

The earlier explicit-three v1.0.0 input draft was never run. It is a local
diagnostic draft only; it is not published or described as failed native
evidence.
