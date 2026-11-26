"""Read and write esf/1 (https://github.com/EVEShipFit/esf-format)."""

import base64
import re

from . import binary, canonical, esi, resolve, sde, source, text, wire
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
from .errors import EsfCatalogError, EsfError, EsfFormatError, EsfRuleError
from .model import BinaryExtra, Document, Entry, EsfFit, Extra, Location, State, TextExtra
from .names import fold

__all__ = [
    "AttributeRecord",
    "BinaryExtra",
    "Catalog",
    "Document",
    "Entry",
    "EsfCatalogError",
    "EsfError",
    "EsfFit",
    "EsfFormatError",
    "EsfRuleError",
    "Extra",
    "Kind",
    "Location",
    "ModeCatalog",
    "MutaplasmidCatalog",
    "MutaplasmidRecord",
    "State",
    "TextExtra",
    "TypeRecord",
    "binary_field",
    "esi",
    "fold",
    "from_base64url",
    "is_text",
    "load",
    "load_document",
    "save",
    "save_binary",
    "sde",
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
        return _canonical(text.parse(data)[0], catalog, fits)
    except EsfError as e:
        if e.line is None:
            raise
        fit, entry = where[e.line - 1]
        raise e._at(fit, entry) from None


def _load(data: bytes | str, catalog: Catalog, keep: bool) -> Document:
    if isinstance(data, str):
        data = data.encode("utf-8", "surrogatepass")
    if not data:
        raise EsfFormatError("the document is empty")
    extra: list[Extra] = []
    if is_text(data):
        blocks, text_extra = text.parse(data, keep)
        fits = _canonical(blocks, catalog)
        extra += text_extra
    else:
        decoded, binary_extra = binary.decode(data)
        fits = _checked(decoded, catalog)
        extra += binary_extra
    return Document([canonical.to_model(f) for f in fits], extra)


def load(data: bytes | str, catalog: Catalog) -> list[EsfFit]:
    """Read a text or binary document, in canonical form."""
    return _load(data, catalog, False).fits


def load_document(data: bytes | str, catalog: Catalog) -> Document:
    """Read a text or binary document, and keep what is not a fit.

    The fits are the same as `load()` returns. A reader skips text blocks and binary
    `Document` fields that are not fits; this hands them back in `Document.extra`, in
    the order of the document. Of the binary fields, only length-delimited ones come
    back. It raises the same errors as `load()`, and one more: a text block whose
    version is above 4294967295 raises `EsfFormatError`, where `load()` skips it.
    """
    return _load(data, catalog, True)


def save(fits: list[EsfFit], catalog: Catalog) -> str:
    """Write fits as canonical text (§8)."""
    return canonical.render(_checked(fits, catalog))


def save_binary(fits: list[EsfFit], catalog: Catalog) -> bytes:
    """Write fits in the binary form (§10)."""
    return binary.encode([canonical.to_model(f) for f in _checked(fits, catalog)])


def binary_field(field: int, data: bytes) -> bytes:
    """A length-delimited `Document` field, to append to the output of `save_binary()`.

    Two binary documents joined are one document, so adding this to the end of
    `save_binary()` output stores `data` next to the fits. `load_document()` hands it
    back as a `BinaryExtra`. `field` is the field number: 2 or more, as 1 holds the
    fits, and at most 536870911. Anything else raises ValueError.
    """
    if not 2 <= field <= wire.MAX_FIELD:
        raise ValueError(f"field must be from 2 to {wire.MAX_FIELD}, not {field}")
    return wire.record(field, bytes(memoryview(data)))


def to_base64url(data: bytes) -> str:
    """The binary form as base64url without padding, for URLs (§10.4)."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def from_base64url(encoded: str) -> bytes:
    """The binary form from base64url without padding (§10.4)."""
    encoded = encoded.strip()
    if not _BASE64URL.fullmatch(encoded) or len(encoded) % 4 == 1:
        raise EsfFormatError("not valid base64url")
    return base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
