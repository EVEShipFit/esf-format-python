"""Read and write esf/1 (https://github.com/EVEShipFit/esf-format)."""

from . import binary, canonical, resolve, text
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
from .names import fold
from .text import EsfError

__all__ = [
    "AttributeRecord",
    "CanonFit",
    "Catalog",
    "EsfError",
    "Kind",
    "ModeCatalog",
    "MutaplasmidCatalog",
    "MutaplasmidRecord",
    "TypeRecord",
    "fold",
    "is_text",
    "read",
    "to_binary",
    "to_text",
]


def is_text(data: bytes) -> bool:
    """Whether a document is text, by its first byte (§10)."""
    return data[:1] in (b"%", b" ")


def read(data: bytes, catalog: Catalog) -> list[CanonFit]:
    """Validate a text or binary document, and return its canonical form."""
    if is_text(data):
        return [
            canonical.canonical_fit(f, catalog) for f in resolve.resolve(text.parse(data), catalog)
        ]
    source, doc = binary.decode(data, catalog)
    fits = resolve.resolve(text.parse(source), catalog)
    binary.verify(fits, doc)
    return [canonical.canonical_fit(f, catalog) for f in fits]


def to_text(fits: list[CanonFit]) -> str:
    return canonical.render(fits)


def to_binary(fits: list[CanonFit]) -> bytes:
    return binary.encode(fits)
