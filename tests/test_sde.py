from typing import NamedTuple

import pytest

from esf_format import Kind, sde


class Named(NamedTuple):
    id: int
    name: str
    published: bool


@pytest.mark.parametrize(
    ("category_id", "group_id", "effect_ids", "expected"),
    [
        pytest.param(6, 25, [5779], Kind.HULL, id="Rifter"),
        pytest.param(65, 1657, [6565], Kind.HULL, id="Astrahus"),
        pytest.param(2, 340, [649], Kind.CONTAINER, id="Small Secure Container"),
        pytest.param(7, 1306, [6010], Kind.MODE, id="Hecate Sharpshooter Mode"),
        pytest.param(32, 954, [896], Kind.SUB, id="Tengu Defensive - Covert Reconfiguration"),
        pytest.param(7, 55, [16, 12, 34], Kind.HIGH, id="200mm AutoCannon II"),
        pytest.param(7, 38, [13, 16], Kind.MID, id="Medium Shield Extender II"),
        pytest.param(7, 60, [11, 16], Kind.LOW, id="Damage Control II"),
        pytest.param(66, 1429, [11, 16], Kind.LOW, id="Standup Ballistic Control System I"),
        pytest.param(7, 774, [446, 2663], Kind.RIG, id="Small Core Defense Field Extender I"),
        pytest.param(66, 1321, [16, 6306], Kind.SVC, id="Standup Cloning Center I"),
        pytest.param(7, 1, [16], Kind.OTHER, id="module without a slot"),
        pytest.param(18, 100, [10], Kind.DRONE, id="Hobgoblin II"),
        pytest.param(87, 1652, [6431], Kind.FIGHTER, id="Templar II"),
        pytest.param(8, 83, [596], Kind.CHARGE, id="Republic Fleet EMP S"),
        pytest.param(20, 1730, [302], Kind.IMPLANT, id="Genolution Core Augmentation CA-1"),
        pytest.param(20, 303, [2737], Kind.BOOSTER, id="Strong Blue Pill Booster"),
        pytest.param(25, 462, [], Kind.OTHER, id="Veldspar"),
    ],
)
def test_kind(category_id: int, group_id: int, effect_ids: list[int], expected: Kind):
    assert sde.kind(category_id, group_id, effect_ids) == expected


def test_active_needs_an_active_or_target_effect():
    assert not sde.active({})
    assert not sde.active({16: 1, 2302: 0})
    assert sde.active({16: 1, 4: 1})
    assert sde.active({16: 1, 3174: 2})


def test_squadron_size():
    assert sde.squadron_size({9: 100.0, 2215: 6.0}) == 6
    assert sde.squadron_size({9: 240.0}) is None


def test_mode_hull_matches_the_longest_ship_name():
    ships = {"hecate": 35683, "hecate navy": 1}
    assert sde.mode_hull("Hecate Sharpshooter Mode", ships) == 35683
    assert sde.mode_hull("Hecate Navy Defense Mode", ships) == 1
    assert sde.mode_hull("Hecate", ships) is None
    assert sde.mode_hull("Rifter Defense Mode", ships) is None


def test_name_index_folds_names_and_picks_published_then_lowest_id():
    entries = [
        Named(50097, "Avatar", False),
        Named(11567, "Avatar", True),
        Named(30, "Twin", False),
        Named(20, "Twin", False),
        Named(587, "Rifter", True),
    ]
    index = sde.name_index(entries, lambda e: e.id, lambda e: e.name, lambda e: e.published)
    assert index == {"avatar": 11567, "twin": 20, "rifter": 587}
