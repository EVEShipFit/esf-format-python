import pytest

from esf_format import Location, esi

_RACKS = {
    Location.HIGH,
    Location.MID,
    Location.LOW,
    Location.RIG,
    Location.SUB,
    Location.SVC,
    Location.TUBE,
}


@pytest.mark.parametrize(
    ("flag", "location", "slot"),
    [
        ("HiSlot0", Location.HIGH, 1),
        ("MedSlot7", Location.MID, 8),
        ("LoSlot2", Location.LOW, 3),
        ("RigSlot1", Location.RIG, 2),
        ("SubSystemSlot3", Location.SUB, 4),
        ("ServiceSlot5", Location.SVC, 6),
        ("FighterTube4", Location.TUBE, 5),
    ],
)
def test_slot(flag: str, location: Location, slot: int) -> None:
    assert esi.location(flag) == location
    assert esi.slot(flag) == slot


def test_every_hold() -> None:
    flags = [
        "Cargo", "DroneBay", "SpecializedAmmoHold", "BoosterBay", "SpecializedCommandCenterHold",
        "CorpseBay", "MobileDepotHold", "ExpeditionHold", "FleetHangar", "FrigateEscapeBay",
        "SpecializedFuelBay", "SpecializedGasHold", "SpecializedIceHold", "InfrastructureHangar",
        "ShipHangar", "SpecializedMineralHold", "SpecializedOreHold", "MoonMaterialBay",
        "SpecializedPlanetaryCommoditiesHold", "QuafeBay", "SubSystemBay",
    ]  # fmt: skip
    assert [esi.location(f) for f in flags] == [loc for loc in Location if loc not in _RACKS]
    assert all(esi.slot(f) is None for f in flags)
    assert esi.location("FighterBay") == Location.BAY


@pytest.mark.parametrize(
    "flag",
    [
        "Hangar",
        "AutoFit",
        "HiSlot8",
        "FighterTube5",
        "hislot0",
        "HiSlot01",
        "HiSlot0\n",
        "toString",
        "",
    ],
)
def test_unknown(flag: str) -> None:
    assert esi.location(flag) is None
    assert esi.slot(flag) is None
