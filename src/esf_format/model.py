"""Fits as type IDs, the way load() returns them and save() takes them (SPEC §5, §10)."""

from dataclasses import dataclass, field
from enum import StrEnum


class State(StrEnum):
    """The state of an item, when not its default (§6.4)."""

    OFF = "off"
    ON = "on"
    HEAT = "heat"


class Location(StrEnum):
    """Where an entry is, when not where its type goes by default (§5)."""

    HIGH = "high"
    MID = "mid"
    LOW = "low"
    RIG = "rig"
    SUB = "sub"
    SVC = "svc"
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


@dataclass
class Entry:
    """One line of a fit."""

    type: int | None
    count: int | None = None
    fit_name: str | None = None
    charge: int | None = None
    charge_count: int | None = None
    mutaplasmid: int | None = None
    overrides: dict[int, float] = field(default_factory=dict)
    state: State | None = None
    location: Location | None = None


@dataclass
class EsfFit:
    """A fit: its hull and its entries."""

    hull: int | None = None
    name: str | None = None
    mode: int | None = None
    entries: list[Entry] = field(default_factory=list)
