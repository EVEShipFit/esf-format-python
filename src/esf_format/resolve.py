"""Resolving names against the Catalog, and the semantic rules (SPEC §4.2, §5, §6)."""

import bisect
import math
from dataclasses import dataclass, field
from enum import StrEnum

from . import catalog as cat
from .catalog import AttributeRecord, Catalog, Kind, MutaplasmidRecord, TypeRecord
from .names import fold, is_word_prefix
from .text import EsfError, FitBlock, Line


class Place(StrEnum):
    """Where an item ends up (§5)."""

    SUB = "sub"
    HIGH = "high"
    MID = "mid"
    LOW = "low"
    RIG = "rig"
    SVC = "svc"
    DRONES = "drones"
    FIGHTERS = "fighters"
    IMPLANTS = "implants"
    BOOSTERS = "boosters"
    CARGO = "cargo"
    BAY = "bay"
    AMMO = "ammo"
    BOOSTER = "booster"
    COMMAND = "command"
    CORPSE = "corpse"
    DEPOT = "depot"
    EXPEDITION = "expedition"
    FLEET = "fleet"
    FRIGATE = "frigate"
    FUEL = "fuel"
    GAS = "gas"
    ICE = "ice"
    INFRASTRUCTURE = "infrastructure"
    MAINTENANCE = "maintenance"
    MINERAL = "mineral"
    MINING = "mining"
    MOON = "moon"
    PLANETARY = "planetary"
    QUAFE = "quafe"
    SUBSYSTEM = "subsystem"


RACKS = (Place.SUB, Place.HIGH, Place.MID, Place.LOW, Place.RIG, Place.SVC)
PLUGGED = (Place.IMPLANTS, Place.BOOSTERS)
STORED = tuple(Place)[list(Place).index(Place.CARGO) :]
DEFAULT_PLACES = {
    Kind.SUB: Place.SUB,
    Kind.HIGH: Place.HIGH,
    Kind.MID: Place.MID,
    Kind.LOW: Place.LOW,
    Kind.RIG: Place.RIG,
    Kind.SVC: Place.SVC,
    Kind.DRONE: Place.DRONES,
    Kind.FIGHTER: Place.FIGHTERS,
    Kind.IMPLANT: Place.IMPLANTS,
    Kind.BOOSTER: Place.BOOSTERS,
}


@dataclass
class Item:
    line: Line
    type: TypeRecord | None
    kind: Kind | None
    place: Place
    charge: TypeRecord | None = None
    mutaplasmid: MutaplasmidRecord | None = None
    overrides: list[tuple[AttributeRecord, float]] = field(default_factory=list)
    reference: "Fit | None" = None

    @property
    def stored(self) -> bool:
        return self.place in STORED


@dataclass
class Fit:
    block: FitBlock
    hull: TypeRecord | None
    mode: TypeRecord | None
    cargo_only: bool
    items: list[Item] = field(default_factory=list)
    racks: dict[Place, list[tuple[int, int, Item | None]]] = field(default_factory=dict)

    @property
    def name(self) -> str | None:
        return self.block.fit_name


def default_place(kind: Kind, cargo_only: bool) -> Place:
    if cargo_only:
        return Place.CARGO
    return DEFAULT_PLACES.get(kind, Place.CARGO)


def mode_name(hull, mode) -> str:
    """A tactical mode's name without the hull's name."""
    return mode.name[len(hull.name) :].lstrip(" ")


def _type(catalog: Catalog, name: str, line: int):
    t = catalog.type(fold(name))
    if t is None:
        raise EsfError(f"unknown type {name!r}", line)
    return t


def _pick(candidates: list, given: str, what: str, line: int, name=lambda c: c.name):
    if not candidates:
        raise EsfError(f"no {what} matches {given!r}", line)
    if len(candidates) > 1:
        names = ", ".join(repr(name(c)) for c in candidates)
        raise EsfError(f"{given!r} matches more than one {what}: {names}", line)
    return candidates[0]


def _resolve_hull(block: FitBlock, catalog: Catalog) -> Fit:
    if block.hull is None:
        return Fit(block, None, None, True)

    hull = _type(catalog, block.hull, block.hull_line)
    if hull.kind not in (Kind.HULL, Kind.CONTAINER):
        raise EsfError(f"{hull.name!r} is not a ship, structure or container", block.hull_line)

    mode = None
    if block.mode is not None:
        modes = cat.modes_of(catalog, hull)
        if not modes:
            raise EsfError(f"{hull.name!r} has no tactical modes", block.hull_line)
        matches = [
            m
            for m in modes
            if is_word_prefix(block.mode, m.name) or is_word_prefix(block.mode, mode_name(hull, m))
        ]
        mode = _pick(matches, block.mode, f"tactical mode of {hull.name!r}", block.hull_line)

    return Fit(block, hull, mode, hull.kind == Kind.CONTAINER)


def _resolve_line(line: Line, fit: Fit, fits: list[Fit], catalog: Catalog) -> Item:
    n = line.number
    if line.kind == "empty":
        if fit.cargo_only:
            raise EsfError("a fit without a ship has no slots to keep empty", n)
        return Item(line, None, None, Place(line.location))

    t = _type(catalog, line.name, n)
    kind = t.kind
    if kind == Kind.MODE:
        raise EsfError("a tactical mode is only written on the hull line", n)

    item = Item(line, t, kind, default_place(kind, fit.cargo_only))

    if line.kind == "reference":
        if kind not in (Kind.HULL, Kind.CONTAINER):
            raise EsfError(f"{t.name!r} cannot take a fit name", n)
        matches = [
            f
            for f in fits
            if f.hull is not None
            and f.hull.id == t.id
            and f.name is not None
            and fold(f.name) == fold(line.fit_name)
        ]
        if len(matches) != 1:
            what = "no fit" if not matches else "more than one fit"
            raise EsfError(f"{what} matches {t.name} {line.fit_name!r}", n)
        item.reference = matches[0]

    if line.index is not None:
        if fit.cargo_only:
            raise EsfError("a fit without a ship stores everything in cargo", n)
        if DEFAULT_PLACES.get(kind) != line.location:
            raise EsfError(f"{t.name!r} does not go in the {line.location} rack", n)
        item.place = Place(line.location)
    elif line.location is not None:
        if fit.cargo_only and line.location != Place.CARGO:
            raise EsfError("a fit without a ship stores everything in cargo", n)
        if line.location == Place.BAY and kind not in (Kind.DRONE, Kind.FIGHTER):
            raise EsfError("@bay is only for drones and fighters", n)
        item.place = Place(line.location)

    if item.place in PLUGGED and line.count is not None:
        raise EsfError("a plugged-in implant or booster takes no count", n)

    if line.state is not None:
        if item.stored:
            raise EsfError("a stored item has no state", n)
        if item.place in PLUGGED and line.state != "off":
            raise EsfError("an implant or booster takes !off only", n)

    if line.charge is not None:
        item.charge = _type(catalog, line.charge, n)
        if item.charge.kind != Kind.CHARGE:
            raise EsfError(f"{item.charge.name!r} is not a charge", n)

    if line.mutaplasmid is not None:
        candidates = cat.mutaplasmids_of(catalog, t)
        matches = [m for m in candidates if is_word_prefix(line.mutaplasmid, m.type.name)]
        item.mutaplasmid = _pick(
            matches, line.mutaplasmid, f"mutaplasmid for {t.name!r}", n, lambda m: m.type.name
        )

    seen = set()
    for name, value in line.overrides:
        attr = catalog.attribute(fold(name))
        if attr is None:
            raise EsfError(f"unknown attribute {name!r}", n)
        if attr.id in seen:
            raise EsfError(f"attribute {attr.name!r} is overridden twice", n)
        seen.add(attr.id)
        number = float(value)
        if not math.isfinite(number):
            raise EsfError(f"value {value!r} is out of range", n)
        item.overrides.append((attr, number))

    return item


def _check_cycles(fits: list[Fit]):
    done: set[int] = set()
    for start in fits:
        if id(start) in done:
            continue
        path = {id(start)}
        stack = [(start, iter(start.items))]
        while stack:
            fit, items = stack[-1]
            item = next((i for i in items if i.reference is not None), None)
            if item is None:
                stack.pop()
                path.discard(id(fit))
                done.add(id(fit))
                continue
            ref = item.reference
            if id(ref) in path:
                raise EsfError("a fit cannot contain itself", item.line.number)
            if id(ref) not in done:
                path.add(id(ref))
                stack.append((ref, iter(ref.items)))


def _layout(items: list[Item]) -> list[tuple[int, int, Item | None]]:
    """Assign slots in one rack (SPEC §6.3): runs of (first index, length, item)."""
    pinned: dict[int, Item] = {}
    for item in items:
        index = item.line.index
        if index is None:
            continue
        if index in pinned:
            raise EsfError(f"slot {index} is pinned twice", item.line.number)
        pinned[index] = item

    pins = sorted(pinned)
    runs = [(index, 1, item) for index, item in pinned.items()]
    pos = 1
    for item in items:
        if item.line.index is not None:
            continue
        remaining = item.line.count or 1
        while remaining:
            while pos in pinned:
                pos += 1
            at = bisect.bisect_left(pins, pos)
            room = pins[at] - pos if at < len(pins) else remaining
            take = min(remaining, room)
            runs.append((pos, take, item))
            pos += take
            remaining -= take
    runs.sort(key=lambda r: r[0])

    filled = []
    pos = 1
    for start, length, item in runs:
        if start > pos:
            filled.append((pos, start - pos, None))
        filled.append((start, length, item))
        pos = start + length
    return filled


def resolve(blocks: list[FitBlock], catalog: Catalog) -> list[Fit]:
    fits = [_resolve_hull(block, catalog) for block in blocks]
    for fit in fits:
        fit.items = [_resolve_line(line, fit, fits, catalog) for line in fit.block.lines]
        plugged = set()
        for item in fit.items:
            if item.place not in PLUGGED:
                continue
            if item.type.id in plugged:
                raise EsfError(f"{item.type.name!r} is plugged in twice", item.line.number)
            plugged.add(item.type.id)
    _check_cycles(fits)
    for fit in fits:
        for rack in RACKS:
            items = [i for i in fit.items if i.place == rack]
            if items:
                fit.racks[rack] = _layout(items)
    return fits
