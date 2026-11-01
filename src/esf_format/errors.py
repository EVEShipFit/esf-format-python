"""The error for a document or fit that breaks a rule of esf/1."""


class EsfError(Exception):
    """A broken rule, and where: a line of text, or a fit and entry, counting from 1."""

    def __init__(
        self,
        message: str,
        line: int | None = None,
        fit: int | None = None,
        entry: int | None = None,
    ):
        super().__init__(message)
        self.message = message
        self.line = line
        self.fit = fit
        self.entry = entry

    def __str__(self) -> str:
        if self.fit is not None:
            where = (
                f"fit {self.fit}" if self.entry is None else f"fit {self.fit}, entry {self.entry}"
            )
            return f"{where}: {self.message}"
        if self.line is not None:
            return f"line {self.line}: {self.message}"
        return self.message
