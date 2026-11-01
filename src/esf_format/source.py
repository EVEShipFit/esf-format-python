"""Fits as the text they stand for, and the check that their IDs match it (SPEC §10.2)."""

import math

from .canonical import number, quote, quote_type
from .catalog import Catalog
from .model import Entry, EsfFit
from .resolve import EmptySlot, Fit
from .text import EsfError


def _name(text: str, what: str) -> str:
    if "\r" in text or "\n" in text:
        raise EsfError(f"{what} contains CR or LF")
    return quote(text)


def _type_name(catalog: Catalog, type_id: int, what: str) -> str:
    t = catalog.type_by_id(type_id)
    if t is None:
        raise EsfError(f"unknown {what} type ID {type_id}")
    return quote_type(t.name)


def _entry(e: Entry, catalog: Catalog) -> str:
    parts = []
    if e.count is not None:
        parts.append(f"{e.count}x")
    parts.append(_type_name(catalog, e.type, "item") if e.type is not None else "-")
    if e.fit_name is not None:
        parts.append(_name(e.fit_name, "a fit name"))
    if e.charge_count is not None and e.charge is None:
        raise EsfError("a charge count is set without a charge")
    if e.charge is not None:
        count = f"{e.charge_count}x " if e.charge_count is not None else ""
        parts.append(f":{count}{_type_name(catalog, e.charge, 'charge')}")
    if e.mutaplasmid is not None:
        parts.append("+" + _type_name(catalog, e.mutaplasmid, "mutaplasmid"))
    if e.overrides:
        pairs = []
        for attribute_id, value in e.overrides.items():
            attribute = catalog.attribute_by_id(attribute_id)
            if attribute is None:
                raise EsfError(f"unknown attribute ID {attribute_id}")
            if not math.isfinite(value):
                raise EsfError("an override value is not finite")
            pairs.append(f"{attribute.name} {number(value)}")
        parts.append("{" + ", ".join(pairs) + "}")
    if e.state is not None:
        parts.append(f"!{e.state}")
    if e.location is not None:
        parts.append(f"@{e.location}")
    return " ".join(parts)


def source(fits: list[EsfFit], catalog: Catalog) -> tuple[bytes, list[str]]:
    """The text document the fits stand for, and which fit or entry each line is."""
    out = []
    where = []
    for n, fit in enumerate(fits, 1):
        try:
            hull = [_type_name(catalog, fit.hull, "hull") if fit.hull is not None else "-"]
            if fit.name is not None:
                hull.append(_name(fit.name, "a fit name"))
            if fit.mode is not None:
                hull.append("/" + _type_name(catalog, fit.mode, "tactical mode"))
        except EsfError as e:
            raise EsfError(f"fit {n}: {e}") from None
        out += ["%esf/1", " ".join(hull)]
        where += [f"fit {n}", f"fit {n}"]
        for m, entry in enumerate(fit.entries, 1):
            try:
                out.append(_entry(entry, catalog))
            except EsfError as e:
                raise EsfError(f"fit {n}, entry {m}: {e}") from None
            where.append(f"fit {n}, entry {m}")
    return "".join(line + "\n" for line in out).encode(), where


def _same(got, want: int | None, what: str):
    got_id = None if got is None else got.id
    if got_id != want:
        raise EsfError(f"{what} ID {want} is not what its name resolves to ({got_id})")


def verify(resolved: list[Fit], fits: list[EsfFit]):
    """Check that every ID is the one its name resolves to."""
    for n, (fit, given) in enumerate(zip(resolved, fits), 1):
        try:
            _same(fit.hull, given.hull, "hull")
            _same(fit.mode, given.mode, "tactical mode")
        except EsfError as e:
            raise EsfError(f"fit {n}: {e}") from None
        for m, (item, entry) in enumerate(zip(fit.items, given.entries), 1):
            if isinstance(item, EmptySlot):
                continue
            try:
                _same(item.type, entry.type, "type")
                _same(item.charge, entry.charge, "charge")
                _same(item.mutaplasmid and item.mutaplasmid.type, entry.mutaplasmid, "mutaplasmid")
                got = [a.id for a, _ in item.overrides]
                if got != list(entry.overrides):
                    raise EsfError(f"attribute IDs {list(entry.overrides)} resolve to {got}")
            except EsfError as e:
                raise EsfError(f"fit {n}, entry {m}: {e}") from None
