"""Read and write esf/1 (https://github.com/EVEShipFit/esf-format)."""

import base64
import re

from . import binary, canonical, resolve, source, text
from .canonical import CanonFit
from .catalog import (
    AttributeRecord,
    Catalog,
    Kind,
    ModeCatalog,
    MutaplasmidCatalog,
    MutaplasmidRecord,
    TypeRecord,
)
from .errors import EsfError
from .model import Entry, EsfFit, Location, State
from .names import fold

__all__ = [
    "AttributeRecord",
    "Catalog",
    "Entry",
    "EsfError",
    "EsfFit",
    "Kind",
    "Location",
    "ModeCatalog",
    "MutaplasmidCatalog",
    "MutaplasmidRecord",
    "State",
    "TypeRecord",
    "fold",
    "from_base64url",
    "is_text",
    "load",
    "save",
    "save_binary",
    "to_base64url",
]

_BASE64URL = re.compile(r"[A-Za-z0-9_-]*")


def is_text(data: bytes | str) -> bool:
    """Whether a document is text, by its first character (§10)."""
    return data[:1] in (b"%", b" ", "%", " ")


def _canonical(
    blocks: list[text.FitBlock], catalog: Catalog, given: list[EsfFit] | None = None
) -> list[CanonFit]:
    fits = resolve.resolve(blocks, catalog)
    if given is not None:
        source.verify(fits, given)
    return [canonical.canonical_fit(f, catalog) for f in fits]


def _checked(fits: list[EsfFit], catalog: Catalog) -> list[CanonFit]:
    data, where = source.source(fits, catalog)
    try:
        return _canonical(text.parse(data), catalog, fits)
    except EsfError as e:
        if e.line is None:
            raise
        fit, entry = where[e.line - 1]
        raise EsfError(e.message, fit=fit, entry=entry) from None


def load(data: bytes | str, catalog: Catalog) -> list[EsfFit]:
    """Read a text or binary document, in canonical form."""
    if isinstance(data, str):
        data = data.encode("utf-8", "surrogatepass")
    if not data:
        raise EsfError("the document is empty")
    if is_text(data):
        fits = _canonical(text.parse(data), catalog)
    else:
        fits = _checked(binary.decode(data), catalog)
    return [canonical.to_model(f) for f in fits]


def save(fits: list[EsfFit], catalog: Catalog) -> str:
    """Write fits as canonical text (§8)."""
    return canonical.render(_checked(fits, catalog))


def save_binary(fits: list[EsfFit], catalog: Catalog) -> bytes:
    """Write fits in the binary form (§10)."""
    return binary.encode([canonical.to_model(f) for f in _checked(fits, catalog)])


def to_base64url(data: bytes) -> str:
    """The binary form as base64url without padding, for URLs (§10.4)."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def from_base64url(encoded: str) -> bytes:
    """The binary form from base64url without padding (§10.4)."""
    encoded = encoded.strip()
    if not _BASE64URL.fullmatch(encoded) or len(encoded) % 4 == 1:
        raise EsfError("not valid base64url")
    return base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
