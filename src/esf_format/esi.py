"""Helpers to turn an ESI `location_flag` into an `Entry.location` and `Entry.slot`.

ESI gives a `location_flag` for each item in a ship, in the assets and fittings
endpoints. Use both helpers on the same flag:

    Entry(type_id, location=esi.location(flag) or Location.CARGO, slot=esi.slot(flag))

Only the flags of things inside a ship are known. For any other flag, like `Hangar`,
both return None. The example above puts those items in the cargo hold.
"""

from .model import Location

_RACKS = (
    ("HiSlot", Location.HIGH, 8),
    ("MedSlot", Location.MID, 8),
    ("LoSlot", Location.LOW, 8),
    ("RigSlot", Location.RIG, 8),
    ("SubSystemSlot", Location.SUB, 8),
    ("ServiceSlot", Location.SVC, 8),
    ("FighterTube", Location.TUBE, 5),
)

_SLOTS = {
    f"{prefix}{i}": (location, i + 1) for prefix, location, size in _RACKS for i in range(size)
}

_HOLDS = {
    "Cargo": Location.CARGO,
    "DroneBay": Location.BAY,
    "FighterBay": Location.BAY,
    "SpecializedAmmoHold": Location.AMMO,
    "BoosterBay": Location.BOOSTER,
    "SpecializedCommandCenterHold": Location.COMMAND,
    "CorpseBay": Location.CORPSE,
    "MobileDepotHold": Location.DEPOT,
    "ExpeditionHold": Location.EXPEDITION,
    "FleetHangar": Location.FLEET,
    "FrigateEscapeBay": Location.FRIGATE,
    "SpecializedFuelBay": Location.FUEL,
    "SpecializedGasHold": Location.GAS,
    "SpecializedIceHold": Location.ICE,
    "InfrastructureHangar": Location.INFRASTRUCTURE,
    "ShipHangar": Location.MAINTENANCE,
    "SpecializedMineralHold": Location.MINERAL,
    "SpecializedOreHold": Location.MINING,
    "MoonMaterialBay": Location.MOON,
    "SpecializedPlanetaryCommoditiesHold": Location.PLANETARY,
    "QuafeBay": Location.QUAFE,
    "SubSystemBay": Location.SUBSYSTEM,
}


def location(flag: str, /) -> Location | None:
    """Gives the `Location` for an ESI `location_flag`.

    A slot flag gives its rack: `HiSlot2` gives `Location.HIGH`, and `FighterTube0`
    gives `Location.TUBE`. `DroneBay` and `FighterBay` give `Location.BAY`. In a fitting
    from ESI, `DroneBay` also holds the drones that are out in space. Leave `Entry.location`
    None for those.

    Returns None for a flag that is not inside a ship, like `Hangar`.
    """
    if flag in _SLOTS:
        return _SLOTS[flag][0]
    return _HOLDS.get(flag)


def slot(flag: str, /) -> int | None:
    """Gives the `Entry.slot` for an ESI `location_flag`, counting from 1.

    ESI counts slots from 0, so `HiSlot2` is slot 3, and `FighterTube0` is tube 1.
    Returns None for a flag that is not a slot, like `Cargo` or `Hangar`.
    """
    found = _SLOTS.get(flag)
    return None if found is None else found[1]
