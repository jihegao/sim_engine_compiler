"""Compilation diagnostics shared by domain validators and compiler passes."""


class CompilationError(ValueError):
    def __init__(self, message: str, *, code: str | None = None, source_path: str | None = None):
        self.code = code
        self.source_path = source_path
        self.message = message
        super().__init__(f"{code} at {source_path}: {message}" if code else message)
