"""Fits as the text they stand for, and the check that their IDs match it (SPEC §10.2)."""

import math

from .canonical import number, quote, quote_type
from .catalog import Catalog
from .errors import EsfError
from .model import Entry, EsfFit
from .resolve import EmptySlot, Fit
from .text import RACKS


def _name(text: str) -> str:
    if "\r" in text or "\n" in text:
        raise EsfError("a fit name contains CR or LF")
    return quote(text)


def _type_name(catalog: Catalog, type_id: int, what: str) -> str:
    t = catalog.type_by_id(type_id)
    if t is None:
        raise EsfError(f"unknown {what} type ID {type_id}")
    return quote_type(t.name)


def _number(value: float) -> str:
    try:
        finite = math.isfinite(value)
    except OverflowError:
        finite = False
    if not finite:
        raise EsfError("an override value is not finite")
    return number(float(value))


def _entry(e: Entry, catalog: Catalog) -> str:
    for n in (e.count, e.charge_count):
        if n is not None and n < 1:
            raise EsfError("a count must be at least 1")
    if e.type is not None and e.location in RACKS:
        raise EsfError("a rack location is only for an empty slot")
    if e.charge_count is not None and e.charge is None:
        raise EsfError("a charge count is set without a charge")

    parts = []
    if e.count is not None:
        parts.append(f"{e.count}x")
    parts.append(_type_name(catalog, e.type, "item") if e.type is not None else "-")
    if e.fit_name:
        parts.append(_name(e.fit_name))
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
            pairs.append(f"{attribute.name} {_number(value)}")
        parts.append("{" + ", ".join(pairs) + "}")
    if e.state is not None:
        parts.append(f"!{e.state}")
    if e.location is not None:
        parts.append(f"@{e.location}")
    return " ".join(parts)


def _hull(fit: EsfFit, catalog: Catalog) -> str:
    hull = [_type_name(catalog, fit.hull, "hull") if fit.hull is not None else "-"]
    if fit.name:
        hull.append(_name(fit.name))
    if fit.mode is not None:
        hull.append("/" + _type_name(catalog, fit.mode, "tactical mode"))
    return " ".join(hull)


def source(fits: list[EsfFit], catalog: Catalog) -> tuple[bytes, list[tuple[int, int | None]]]:
    """The text document the fits stand for, and the (fit, entry) each line is."""
    if not fits:
        raise EsfError("a document holds at least one fit")
    out = []
    where: list[tuple[int, int | None]] = []
    for n, fit in enumerate(fits, 1):
        try:
            out += ["%esf/1", _hull(fit, catalog)]
        except EsfError as e:
            raise EsfError(e.message, fit=n) from None
        where += [(n, None), (n, None)]
        for m, entry in enumerate(fit.entries, 1):
            try:
                out.append(_entry(entry, catalog))
            except EsfError as e:
                raise EsfError(e.message, fit=n, entry=m) from None
            where.append((n, m))
    return "".join(line + "\n" for line in out).encode(), where


def _same(got: object, want: int | None, what: str) -> None:
    got_id = getattr(got, "id", None)
    if got_id != want:
        raise EsfError(f"{what} ID {want} is not what its name resolves to ({got_id})")


def verify(resolved: list[Fit], fits: list[EsfFit]) -> None:
    """Check that every ID is the one its name resolves to."""
    for n, (fit, given) in enumerate(zip(resolved, fits), 1):
        try:
            _same(fit.hull, given.hull, "hull")
            _same(fit.mode, given.mode, "tactical mode")
        except EsfError as e:
            raise EsfError(e.message, fit=n) from None
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
                raise EsfError(e.message, fit=n, entry=m) from None
