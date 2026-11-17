"""Fits as type IDs, the way load() returns them and save() takes them (SPEC §5, §6.3, §10)."""

from dataclasses import dataclass, field
from enum import StrEnum


class State(StrEnum):
    """Whether an item is offline, online or running, when not its default (esf/1 spec §6.4).

    By default, a fitted or deployed item runs when its type is `TypeRecord.active`, and is
    online otherwise. An implant or booster is online by default, and only takes OFF.
    A stored item, in cargo, a bay or a hold, has no state at all.
    """

    OFF = "off"
    """Offline: fitted, but not using powergrid or CPU."""

    ON = "on"
    """Online, but not running, like a gun that is not shooting."""

    HEAT = "heat"
    """Overloaded, which also means running."""


class Location(StrEnum):
    """Where an entry goes, when not where its type goes by default (esf/1 spec §5).

    An item goes where its `Kind` says, so most entries leave this None. Set it to store an
    item somewhere else, like a spare Damage Control II in CARGO.
    So a drone with no location is out in space, and a fighter is in a launch tube. Set
    BAY to keep either one in its bay.

    The racks, HIGH to SVC and TUBE, are for empty slots, and for an item put in a given
    `Entry.slot`. Otherwise, an item never names its rack.
    The holds, AMMO to SUBSYSTEM, only make sense on a hull that has that hold, but the
    library does not check that.
    """

    HIGH = "high"
    """The high slot rack."""

    MID = "mid"
    """The mid slot rack."""

    LOW = "low"
    """The low slot rack."""

    RIG = "rig"
    """The rig rack."""

    SUB = "sub"
    """The subsystem rack. Not the same as SUBSYSTEM, which is a hold."""

    SVC = "svc"
    """The structure service rack."""

    CARGO = "cargo"
    """The cargo hold."""

    BAY = "bay"
    """The drone bay or fighter bay, for drones and fighters not out in space or in a tube."""

    AMMO = "ammo"
    """The Ammo Hold."""

    BOOSTER = "booster"
    """The Booster Hold."""

    COMMAND = "command"
    """The Command Center Hold."""

    CORPSE = "corpse"
    """The Corpse Hold."""

    DEPOT = "depot"
    """The Mobile Depot Hold."""

    EXPEDITION = "expedition"
    """The Expedition Hold."""

    FLEET = "fleet"
    """The Fleet Hangar."""

    FRIGATE = "frigate"
    """The Frigate Escape Bay."""

    FUEL = "fuel"
    """The Fuel Bay."""

    GAS = "gas"
    """The Gas Hold."""

    ICE = "ice"
    """The Ice Hold."""

    INFRASTRUCTURE = "infrastructure"
    """The Infrastructure Hold."""

    MAINTENANCE = "maintenance"
    """The Ship Maintenance Bay."""

    MINERAL = "mineral"
    """The Mineral Hold."""

    MINING = "mining"
    """The Mining Hold."""

    MOON = "moon"
    """The Moon Material Output Bay."""

    PLANETARY = "planetary"
    """The Planetary Commodities Hold."""

    QUAFE = "quafe"
    """The Quafe Hold."""

    SUBSYSTEM = "subsystem"
    """The Subsystem Hold, for spare subsystems. Not the same as SUB, which is the rack."""

    TUBE = "tube"
    """The fighter launch tubes."""


@dataclass
class Entry:
    """One line of a fit: an item, an empty slot, or another fit carried by this one.

    Only `type` is needed; every other field is None or empty when it is the default.
    Entries can be in any order, except within a rack: there, the order is the slot order,
    unless an entry sets `slot`.
    """

    type: int | None
    """The type ID of the item, like 2889 for a 200mm AutoCannon II.

    None for an empty slot. An empty slot must set `location` to its rack, like
    `Location.HIGH`.
    """

    count: int | None = None
    """How many there are. None means one.

    What a count means depends on where the item goes (esf/1 spec §6.2). For a fitted
    module or a deployed drone, it is that many of the same line: 3 guns take 3 slots.
    For a stored item, it is the size of one stack. For a fighter, it is how many are
    in the squadron; None means a full squadron. A plugged-in implant or booster takes
    no count.
    """

    fit_name: str | None = None
    """The name of another fit in the same list, which this entry carries.

    Only for a type whose `Kind.can_be_hull` is true. The other fit must have this
    entry's `type` as its `EsfFit.hull` and this as its `EsfFit.name`, ignoring case.
    For example, a Heron with fit name "Scout" and `Location.FRIGATE` carries that fit
    in the Frigate Escape Bay. None means an unfitted ship or an empty container.
    """

    charge: int | None = None
    """The type ID of the charge loaded into this item, like ammunition or a script.

    None for none.
    """

    charge_count: int | None = None
    """How many of `charge` are loaded into each item.

    None means a full load: the item's capacity divided by the charge's volume, rounded
    down. Only set together with `charge`.
    """

    mutaplasmid: int | None = None
    """The type ID of the mutaplasmid applied to this item, which makes it abyssal.

    `type` is then the base type the mutaplasmid applies to, and `overrides` holds the
    rolled values. None for a normal item.
    """

    overrides: dict[int, float] = field(default_factory=dict)
    """Dogma attribute values that replace the type's own, by attribute ID.

    For example {20: 524.0} sets speedFactor (20) to 524.0. Each value is the new base
    value, not a change on top of it. Attributes not listed keep the type's value.
    Empty for none.
    """

    state: State | None = None
    """Whether the item is offline, online or running. None means its default; see `State`."""

    location: Location | None = None
    """Where the item goes. None means where its type goes by default; see `Location`."""

    slot: int | None = None
    """The slot in the `location` rack, counting from 1, like 3 for the third high slot.

    Set `location` to the rack too, and the item must go in that rack. A slot can't be
    combined with `count`, except for a fighter in `Location.TUBE`, where the count is
    the squadron's size. Each slot in a rack can be pinned only once. None means the
    next free slot. `esf_format.load()` never sets this: it gives the rack in slot order,
    with empty slots in between.
    """


@dataclass
class EsfFit:
    """One fit: a ship and everything on it, or a plain list of items.

    A list of fits is one document. A fit that another fit carries, through
    `Entry.fit_name`, exists only there. Any other fit stands on its own.
    """

    hull: int | None = None
    """The type ID of the ship, structure or container, like 587 for the Rifter.

    Only a type whose `Kind.can_be_hull` is true can be a hull.

    None for a fit without a ship, like the items in a contract: then every entry is
    stored in cargo, and the fit has no slots and no `mode`.
    """

    name: str | None = None
    """The name of the fit, like "Shield Buffer". None for no name."""

    mode: int | None = None
    """The type ID of the tactical mode the ship is in, like the Hecate's Sharpshooter Mode.

    Only for a hull that has tactical modes; see `ModeCatalog.modes()`. None for none.
    """

    entries: list[Entry] = field(default_factory=list)
    """The lines of the fit: items, empty slots and fits it carries."""
