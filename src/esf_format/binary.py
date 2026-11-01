"""The binary form (SPEC §10)."""

import math
import struct
from dataclasses import dataclass, field

from . import wire
from .canonical import CanonFit, number, quote, quote_type
from .catalog import Catalog
from .resolve import Fit
from .text import EsfError

STATES = (None, "off", "on", "heat")
LOCATIONS = (
    None,
    "high",
    "mid",
    "low",
    "rig",
    "sub",
    "svc",
    "cargo",
    "bay",
    "ammo",
    "booster",
    "command",
    "corpse",
    "depot",
    "expedition",
    "fleet",
    "frigate",
    "fuel",
    "gas",
    "ice",
    "infrastructure",
    "maintenance",
    "mineral",
    "mining",
    "moon",
    "planetary",
    "quafe",
    "subsystem",
)


@dataclass
class Entry:
    type: int | None = None
    count: int | None = None
    fit_name: str = ""
    charge: int | None = None
    charge_count: int | None = None
    mutaplasmid: int | None = None
    override_attributes: list[int] = field(default_factory=list)
    override_values: list[float] = field(default_factory=list)
    state: int = 0
    location: int = 0


@dataclass
class BinaryFit:
    version: int = 0
    hull: int | None = None
    name: str = ""
    tactical_mode: int | None = None
    entries: list[Entry] = field(default_factory=list)


def _encode_entry(line) -> bytes:
    out = b""
    if line.type is not None:
        out += wire.uint(1, line.type.id)
    if line.count is not None:
        out += wire.uint(2, line.count)
    if line.fit_name:
        out += wire.record(3, line.fit_name.encode())
    if line.charge is not None:
        out += wire.uint(4, line.charge.id)
    if line.charge_count is not None:
        out += wire.uint(5, line.charge_count)
    if line.mutaplasmid is not None:
        out += wire.uint(6, line.mutaplasmid.type.id)
    if line.overrides:
        out += wire.packed_uints(7, [a.id for a, _ in line.overrides])
        out += wire.packed_doubles(8, [v for _, v in line.overrides])
    if line.state is not None:
        out += wire.uint(9, STATES.index(line.state))
    if line.location is not None:
        out += wire.uint(10, LOCATIONS.index(line.location))
    return out


def _encode_fit(fit: CanonFit) -> bytes:
    out = wire.uint(1, 1)
    if fit.hull is not None:
        out += wire.uint(2, fit.hull.id)
    if fit.name:
        out += wire.record(3, fit.name.encode())
    if fit.mode is not None:
        out += wire.uint(4, fit.mode.id)
    for line in fit.lines:
        out += wire.record(5, _encode_entry(line))
    return out


def encode(fits: list[CanonFit]) -> bytes:
    return b"".join(wire.record(1, _encode_fit(fit)) for fit in fits)


def _uint32(value: int, what: str) -> int:
    if value > 0xFFFFFFFF:
        raise EsfError(f"binary: {what} is out of range")
    return value


def _string(payload: bytes, what: str) -> str:
    try:
        return payload.decode("utf-8")
    except UnicodeDecodeError:
        raise EsfError(f"binary: {what} is not valid UTF-8") from None


def _not_in_schema(what: str):
    return EsfError(f"binary: {what} has a field that is not in the schema")


def _parse_entry(data: bytes) -> Entry:
    e = Entry()
    for tag, wire_type, value in wire.fields(data):
        match tag, wire_type:
            case 1, wire.VARINT:
                e.type = _uint32(value, "Entry.type")
            case 2, wire.VARINT:
                e.count = _uint32(value, "Entry.count")
            case 3, wire.LEN:
                e.fit_name = _string(value, "Entry.fit_name")
            case 4, wire.VARINT:
                e.charge = _uint32(value, "Entry.charge")
            case 5, wire.VARINT:
                e.charge_count = _uint32(value, "Entry.charge_count")
            case 6, wire.VARINT:
                e.mutaplasmid = _uint32(value, "Entry.mutaplasmid")
            case 7, wire.VARINT:
                e.override_attributes.append(_uint32(value, "Entry.override_attributes"))
            case 7, wire.LEN:
                e.override_attributes += [
                    _uint32(v, "Entry.override_attributes") for v in wire.unpack_uints(value)
                ]
            case 8, wire.I64:
                e.override_values.append(struct.unpack("<d", value)[0])
            case 8, wire.LEN:
                e.override_values += wire.unpack_doubles(value)
            case 9, wire.VARINT:
                e.state = value
            case 10, wire.VARINT:
                e.location = value
            case _:
                raise _not_in_schema("Entry")
    return e


def _parse_fit(data: bytes) -> BinaryFit:
    f = BinaryFit()
    for tag, wire_type, value in wire.fields(data):
        match tag, wire_type:
            case 1, wire.VARINT:
                f.version = _uint32(value, "Fit.version")
            case 2, wire.VARINT:
                f.hull = _uint32(value, "Fit.hull")
            case 3, wire.LEN:
                f.name = _string(value, "Fit.name")
            case 4, wire.VARINT:
                f.tactical_mode = _uint32(value, "Fit.tactical_mode")
            case 5, wire.LEN:
                f.entries.append(_parse_entry(value))
            case _:
                raise _not_in_schema("Fit")
    return f


def _parse(data: bytes) -> list[BinaryFit]:
    fits = []
    for tag, wire_type, value in wire.fields(data):
        if tag != 1:
            continue
        if wire_type != wire.LEN:
            raise EsfError("binary: Document.fits has the wrong wire type")
        fits.append(_parse_fit(value))
    return fits


def _enum(names: tuple, value: int, what: str) -> str | None:
    if value >= len(names):
        raise EsfError(f"binary: unknown {what} value {value}")
    return names[value]


def _name(text: str, what: str) -> str:
    if "\r" in text or "\n" in text:
        raise EsfError(f"binary: {what} contains CR or LF")
    return quote(text)


def _type_name(catalog: Catalog, type_id: int, what: str) -> str:
    t = catalog.type_by_id(type_id)
    if t is None:
        raise EsfError(f"binary: unknown {what} type ID {type_id}")
    return quote_type(t.name)


def _entry(e: Entry, catalog: Catalog) -> str:
    parts = []
    if e.count is not None:
        parts.append(f"{e.count}x")
    parts.append(_type_name(catalog, e.type, "item") if e.type is not None else "-")
    if e.fit_name:
        parts.append(_name(e.fit_name, "Entry.fit_name"))
    if e.charge_count is not None and e.charge is None:
        raise EsfError("binary: charge_count is set without charge")
    if e.charge is not None:
        count = f"{e.charge_count}x " if e.charge_count is not None else ""
        parts.append(f":{count}{_type_name(catalog, e.charge, 'charge')}")
    if e.mutaplasmid is not None:
        parts.append("+" + _type_name(catalog, e.mutaplasmid, "mutaplasmid"))
    if len(e.override_attributes) != len(e.override_values):
        raise EsfError("binary: override fields have different lengths")
    if e.override_attributes:
        pairs = []
        for attr_id, value in zip(e.override_attributes, e.override_values):
            attr = catalog.attribute_by_id(attr_id)
            if attr is None:
                raise EsfError(f"binary: unknown attribute ID {attr_id}")
            if not math.isfinite(value):
                raise EsfError("binary: an override value is not finite")
            pairs.append(f"{attr.name} {number(value)}")
        parts.append("{" + ", ".join(pairs) + "}")
    if state := _enum(STATES, e.state, "State"):
        parts.append("!" + state)
    if location := _enum(LOCATIONS, e.location, "Location"):
        parts.append("@" + location)
    return " ".join(parts)


def decode(data: bytes, catalog: Catalog) -> tuple[bytes, list[BinaryFit]]:
    """Map a binary document to the text it stands for."""
    if not data:
        raise EsfError("binary: the document is empty")
    doc = _parse(data)

    out = []
    for f in doc:
        if f.version != 1:
            raise EsfError(f"binary: unsupported Fit.version {f.version}")
        hull = [_type_name(catalog, f.hull, "hull") if f.hull is not None else "-"]
        if f.name:
            hull.append(_name(f.name, "Fit.name"))
        if f.tactical_mode is not None:
            hull.append("/" + _type_name(catalog, f.tactical_mode, "tactical mode"))
        out += ["%esf/1", " ".join(hull)]
        out += [_entry(e, catalog) for e in f.entries]
        out.append("")
    return "\n".join(out).encode(), doc


def verify(fits: list[Fit], doc: list[BinaryFit]):
    """Check that every ID is the one its name resolves to."""

    def same(got, want: int | None, what: str):
        got_id = None if got is None else got.id
        if got_id != want:
            raise EsfError(f"binary: {what} ID {want} is not what its name resolves to ({got_id})")

    for fit, f in zip(fits, doc):
        same(fit.hull, f.hull, "hull")
        same(fit.mode, f.tactical_mode, "tactical mode")
        for item, e in zip(fit.items, f.entries):
            same(item.type, e.type, "type")
            same(item.charge, e.charge, "charge")
            muta = item.mutaplasmid.type if item.mutaplasmid else None
            same(muta, e.mutaplasmid, "mutaplasmid")
            got = [a.id for a, _ in item.overrides]
            if got != e.override_attributes:
                raise EsfError(f"binary: attribute IDs {e.override_attributes} resolve to {got}")
