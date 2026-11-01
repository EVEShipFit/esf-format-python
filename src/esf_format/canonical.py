"""Canonical form (SPEC §8)."""

from dataclasses import dataclass, field
from decimal import Decimal

from . import catalog as cat
from .catalog import AttributeRecord, Catalog, MutaplasmidRecord, TypeRecord
from .names import fold, shortest_unique
from .resolve import DEFAULT_PLACES, PLUGGED, RACKS, Fit, Item, Place, default_place, mode_name
from .text import SIGILS, is_count

GROUPS = (
    Place.SUB,
    Place.HIGH,
    Place.MID,
    Place.LOW,
    Place.RIG,
    Place.SVC,
    Place.DRONES,
    Place.FIGHTERS,
    Place.CARGO,
    Place.AMMO,
    Place.BOOSTER,
    Place.COMMAND,
    Place.CORPSE,
    Place.DEPOT,
    Place.EXPEDITION,
    Place.FLEET,
    Place.FRIGATE,
    Place.FUEL,
    Place.GAS,
    Place.ICE,
    Place.INFRASTRUCTURE,
    Place.MAINTENANCE,
    Place.MINERAL,
    Place.MINING,
    Place.MOON,
    Place.PLANETARY,
    Place.QUAFE,
    Place.SUBSYSTEM,
    Place.IMPLANTS,
    Place.BOOSTERS,
)


@dataclass
class CanonLine:
    type: TypeRecord | None
    count: int | None = None
    fit_name: str | None = None
    charge: TypeRecord | None = None
    charge_count: int | None = None
    mutaplasmid: MutaplasmidRecord | None = None
    mutaplasmid_name: str | None = None
    overrides: list[tuple[AttributeRecord, float]] = field(default_factory=list)
    state: str | None = None
    location: str | None = None

    def body(self) -> str:
        parts = [quote_type(self.type.name) if self.type else "-"]
        if self.fit_name is not None:
            parts.append(quote(self.fit_name))
        if self.charge is not None:
            count = "" if self.charge_count is None else f"{self.charge_count}x "
            parts.append(f":{count}{quote_type(self.charge.name)}")
        if self.mutaplasmid is not None:
            parts.append(f"+{self.mutaplasmid_name}")
        if self.overrides:
            pairs = ", ".join(f"{a.name} {number(v)}" for a, v in self.overrides)
            parts.append(f"{{{pairs}}}")
        if self.state is not None:
            parts.append(f"!{self.state}")
        if self.location is not None:
            parts.append(f"@{self.location}")
        return " ".join(parts)

    def text(self) -> str:
        if self.count is None:
            return self.body()
        return f"{self.count}x {self.body()}"


@dataclass
class CanonFit:
    hull: TypeRecord | None
    name: str | None
    mode: TypeRecord | None
    mode_text: str | None
    groups: list[list[CanonLine]]

    @property
    def lines(self) -> list[CanonLine]:
        return [line for group in self.groups for line in group]

    def text(self) -> str:
        hull = [quote_type(self.hull.name) if self.hull else "-"]
        if self.name is not None:
            hull.append(quote(self.name))
        if self.mode is not None:
            hull.append(f"/{self.mode_text}")
        out = f"%esf/1\n{' '.join(hull)}\n"
        for group in self.groups:
            out += "\n" + "".join(line.text() + "\n" for line in group)
        return out


def quote(s: str) -> str:
    return '"' + s.replace('"', '""') + '"'


def needs_quotes(name: str) -> bool:
    words = name.split(" ")
    return (
        words[0][:1] in ("-", "%", "")
        or is_count(words[0])
        or any(w[:1] in SIGILS or w == "" for w in words)
    )


def quote_type(name: str) -> str:
    return quote(name) if needs_quotes(name) else name


def number(value: float) -> str:
    """The shortest decimal, without exponent, that reads back as the same float."""
    if value == 0:
        value = 0.0
    text = repr(value)
    if "e" in text or "E" in text:
        text = format(Decimal(text), "f")
    text = text.removesuffix(".0")
    return text


def _default_state(item: Item, catalog: Catalog) -> str | None:
    """The state token that canonical form leaves out; None means running."""
    if item.place in PLUGGED or not item.type.active:
        return "on"
    return None


def _line(item: Item, fit: Fit, catalog: Catalog) -> CanonLine:
    line = item.line
    out = CanonLine(item.type)

    if item.reference is not None:
        out.fit_name = item.reference.name

    if item.charge is not None:
        out.charge = item.charge
        full = cat.full_load(item.type, item.charge)
        if line.charge_count is not None and line.charge_count != full:
            out.charge_count = line.charge_count

    overrides = {a.id: (a, v or 0.0) for a, v in item.overrides}
    if item.mutaplasmid is not None:
        out.mutaplasmid = item.mutaplasmid
        own = item.mutaplasmid.type.name
        others = [m.type.name for m in cat.mutaplasmids_of(catalog, item.type)]
        others.remove(own)
        out.mutaplasmid_name = shortest_unique(own, others)
        for attr_id, base in item.mutaplasmid.rolls:
            if attr_id not in overrides:
                overrides[attr_id] = (catalog.attribute_by_id(attr_id), base)
    out.overrides = sorted(overrides.values(), key=lambda o: (fold(o[0].name), o[0].name))

    if line.state is not None and line.state != _default_state(item, catalog):
        out.state = line.state

    if item.place != default_place(item.kind, fit.cargo_only) and item.place not in RACKS:
        out.location = item.place
    return out


def _sort_key(type_, text: str):
    return (fold(type_.name), text.encode())


def _collapse(lines: list[tuple[bool, CanonLine]]) -> list[CanonLine]:
    """Merge adjacent identical repeatable lines into one count."""
    out: list[tuple[bool, CanonLine]] = []
    for repeatable, line in lines:
        if out and repeatable and out[-1][0] and out[-1][1].body() == line.body():
            prev = out[-1][1]
            prev.count = (prev.count or 1) + (line.count or 1)
            continue
        out.append((repeatable, line))
    for _, line in out:
        if line.count == 1:
            line.count = None
    return [line for _, line in out]


def _rack(fit: Fit, rack: Place, catalog: Catalog) -> list[CanonLine]:
    runs = list(fit.racks.get(rack, []))
    while runs and (runs[-1][2] is None or runs[-1][2].type is None):
        runs.pop()
    lines = []
    for _, length, item in runs:
        if item is None or item.type is None:
            line = CanonLine(None, location=rack)
        else:
            line = _line(item, fit, catalog)
        line.count = length
        lines.append((True, line))
    return _collapse(lines)


def _sorted(items: list[Item], fit: Fit, catalog: Catalog) -> list[CanonLine]:
    lines = []
    for item in items:
        line = _line(item, fit, catalog)
        repeatable = not item.stored
        count = item.line.count or 1
        if repeatable:
            line.count = count
            key = _sort_key(item.type, line.body())
        else:
            line.count = None if count == 1 else count
            key = _sort_key(item.type, line.text())
        lines.append((key, repeatable, line))
    lines.sort(key=lambda entry: entry[0])
    return _collapse([(repeatable, line) for _, repeatable, line in lines])


def _fighters(items: list[Item], fit: Fit, catalog: Catalog) -> list[CanonLine]:
    tubes = [i for i in items if i.place == Place.FIGHTERS]
    lines = []
    for item in tubes:
        line = _line(item, fit, catalog)
        count = item.line.count
        if count is not None and count != item.type.squadron_size:
            line.count = count
        lines.append(line)
    return lines + _sorted([i for i in items if i.place == Place.BAY], fit, catalog)


def canonical_fit(fit: Fit, catalog: Catalog) -> CanonFit:
    groups: dict[Place, list[Item]] = {}
    for item in fit.items:
        if item.place in RACKS:
            continue
        group = item.place
        if group == Place.BAY:
            group = DEFAULT_PLACES[item.kind]
        groups.setdefault(group, []).append(item)

    chunks = []
    for group in GROUPS:
        if group in RACKS:
            chunk = _rack(fit, group, catalog)
        elif group == Place.FIGHTERS:
            chunk = _fighters(groups.get(group, []), fit, catalog)
        else:
            chunk = _sorted(groups.get(group, []), fit, catalog)
        if chunk:
            chunks.append(chunk)

    mode_text = None
    if fit.mode is not None:
        others = [mode_name(fit.hull, m) for m in cat.modes_of(catalog, fit.hull)]
        own = mode_name(fit.hull, fit.mode)
        others.remove(own)
        mode_text = shortest_unique(own, others)

    return CanonFit(fit.hull, fit.name, fit.mode, mode_text, chunks)


def render(fits: list[CanonFit]) -> str:
    return "\n".join(fit.text() for fit in fits)
