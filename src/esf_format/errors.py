"""The errors of esf/1."""

from typing import Self


class EsfError(Exception):
    """An esf/1 error, and where: a line of text, or a fit and entry, counting from 1.

    Every error is one of three kinds. Catch `EsfFormatError`, `EsfCatalogError` or
    `EsfRuleError` to handle one kind, or this class to handle them all.
    """

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

    def _at(self, fit: int, entry: int | None = None) -> Self:
        return type(self)(self.message, fit=fit, entry=entry)


class EsfFormatError(EsfError):
    """The data is not a well-formed esf/1 document.

    The text does not follow the grammar, the binary form or base64url is broken, or a fit
    name cannot be written.
    """


class EsfCatalogError(EsfError):
    """The catalog does not know a name or ID, or a name matches more than one type.

    This often means the catalog is older than the fit.
    """


class EsfRuleError(EsfError):
    """The fit breaks a rule of esf/1.

    The document is well formed and the catalog knows every type, but the fit is not valid.
    For example, a module is in the wrong rack.
    """
