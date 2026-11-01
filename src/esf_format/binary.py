"""The binary form (SPEC §10)."""

import struct

from . import wire
from .model import Entry, EsfFit, Location, State
from .text import UINT32_MAX, EsfError

STATES = (None, *State)
LOCATIONS = (None, *Location)


def _encode_entry(entry: Entry) -> bytes:
    out = b""
    if entry.type is not None:
        out += wire.uint(1, entry.type)
    if entry.count is not None:
        if entry.count > UINT32_MAX:
            raise EsfError(f"binary: a count of {entry.count} is too large")
        out += wire.uint(2, entry.count)
    if entry.fit_name:
        out += wire.record(3, entry.fit_name.encode())
    if entry.charge is not None:
        out += wire.uint(4, entry.charge)
    if entry.charge_count is not None:
        out += wire.uint(5, entry.charge_count)
    if entry.mutaplasmid is not None:
        out += wire.uint(6, entry.mutaplasmid)
    if entry.overrides:
        out += wire.packed_uints(7, list(entry.overrides))
        out += wire.packed_doubles(8, list(entry.overrides.values()))
    if entry.state is not None:
        out += wire.uint(9, STATES.index(entry.state))
    if entry.location is not None:
        out += wire.uint(10, LOCATIONS.index(entry.location))
    return out


def _encode_fit(fit: EsfFit) -> bytes:
    out = wire.uint(1, 1)
    if fit.hull is not None:
        out += wire.uint(2, fit.hull)
    if fit.name:
        out += wire.record(3, fit.name.encode())
    if fit.mode is not None:
        out += wire.uint(4, fit.mode)
    for entry in fit.entries:
        out += wire.record(5, _encode_entry(entry))
    return out


def encode(fits: list[EsfFit]) -> bytes:
    return b"".join(wire.record(1, _encode_fit(fit)) for fit in fits)


def _uint32(value: int, what: str) -> int:
    if value > UINT32_MAX:
        raise EsfError(f"binary: {what} is out of range")
    return value


def _string(payload: bytes, what: str) -> str | None:
    try:
        return payload.decode("utf-8") or None
    except UnicodeDecodeError:
        raise EsfError(f"binary: {what} is not valid UTF-8") from None


def _enum(values: tuple, value: int, what: str):
    if value >= len(values):
        raise EsfError(f"binary: unknown {what} value {value}")
    return values[value]


def _not_in_schema(what: str) -> EsfError:
    return EsfError(f"binary: {what} has a field that is not in the schema")


def _decode_entry(data: bytes) -> Entry:
    e = Entry(None)
    attributes: list[int] = []
    values: list[float] = []
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
                attributes.append(_uint32(value, "Entry.override_attributes"))
            case 7, wire.LEN:
                attributes += [
                    _uint32(v, "Entry.override_attributes") for v in wire.unpack_uints(value)
                ]
            case 8, wire.I64:
                values.append(struct.unpack("<d", value)[0])
            case 8, wire.LEN:
                values += wire.unpack_doubles(value)
            case 9, wire.VARINT:
                e.state = _enum(STATES, value, "State")
            case 10, wire.VARINT:
                e.location = _enum(LOCATIONS, value, "Location")
            case _:
                raise _not_in_schema("Entry")
    if len(attributes) != len(values):
        raise EsfError("binary: override fields have different lengths")
    e.overrides = dict(zip(attributes, values))
    if len(e.overrides) != len(attributes):
        raise EsfError("binary: an attribute is overridden twice")
    return e


def _decode_fit(data: bytes) -> EsfFit:
    fit = EsfFit()
    version = 0
    for tag, wire_type, value in wire.fields(data):
        match tag, wire_type:
            case 1, wire.VARINT:
                version = _uint32(value, "Fit.version")
            case 2, wire.VARINT:
                fit.hull = _uint32(value, "Fit.hull")
            case 3, wire.LEN:
                fit.name = _string(value, "Fit.name")
            case 4, wire.VARINT:
                fit.mode = _uint32(value, "Fit.tactical_mode")
            case 5, wire.LEN:
                fit.entries.append(_decode_entry(value))
            case _:
                raise _not_in_schema("Fit")
    if version != 1:
        raise EsfError(f"binary: unsupported Fit.version {version}")
    return fit


def decode(data: bytes) -> list[EsfFit]:
    if not data:
        raise EsfError("binary: the document is empty")
    fits = []
    for tag, wire_type, value in wire.fields(data):
        if tag != 1:
            continue
        if wire_type != wire.LEN:
            raise EsfError("binary: Document.fits has the wrong wire type")
        fits.append(_decode_fit(value))
    return fits
