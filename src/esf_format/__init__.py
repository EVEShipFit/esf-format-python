"""Read and write esf/1 (https://github.com/EVEShipFit/esf-format)."""

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
from .model import Entry, EsfFit, Location, State
from .names import fold
from .text import EsfError

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
    "is_text",
    "load",
    "save",
    "save_binary",
]


def is_text(data: bytes) -> bool:
    """Whether a document is text, by its first byte (§10)."""
    return data[:1] in (b"%", b" ")


def _canonical(blocks: list[text.FitBlock], catalog: Catalog, given: list[EsfFit] | None = None):
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
        raise EsfError(f"{where[e.line - 1]}: {e.message}") from None


def load(data: bytes, catalog: Catalog) -> list[EsfFit]:
    """Read a text or binary document, in canonical form."""
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
