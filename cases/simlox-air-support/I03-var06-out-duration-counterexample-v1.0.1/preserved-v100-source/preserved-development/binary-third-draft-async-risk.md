# Author helper async-drain risk before source freeze

This mutable third draft passed local PowerShell 5 exit0/7, original 10-byte invalid UTF-8/NUL/CRLF streams, injected observation and synchronous drain-setup failures. Independent static review noted a separate asynchronous `CopyToAsync` fault could leave a child with large output blocked before `WaitForExit`. The exact helper/test/child bytes are preserved. No large-output/async-fault test had run on this draft and no SIMLOX was invoked.
