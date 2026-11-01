import math
import os

import pytest
from catalog import JsonCatalog

from esf_format import Entry, EsfError, EsfFit, Location, State, load, save, save_binary

CATALOG = JsonCatalog(os.environ.get("ESF_CATALOG", "esf-format/tests/catalog.json"))

RIFTER = 587
AUTOCANNON = 2889
EMP = 21898
SHIELD_EXTENDER = 3831
SCRAMBLER = 448
DAMAGE_CONTROL = 2048
HOBGOBLIN = 2456
DECAYED_DAMAGE_CONTROL_MUTAPLASMID = 52224
AVATAR = 11567
AVATAR_UNPUBLISHED = 50097
SMALL_SECURE_CONTAINER = 3467


def fit(*entries: Entry, **kwargs) -> EsfFit:
    return EsfFit(RIFTER, **kwargs, entries=list(entries))


def test_save_canonical():
    rifter = fit(
        Entry(DAMAGE_CONTROL),
        Entry(AUTOCANNON, charge=EMP),
        Entry(SHIELD_EXTENDER),
        Entry(AUTOCANNON, charge=EMP),
        Entry(None, location=Location.HIGH),
        Entry(SCRAMBLER, state=State.OFF),
        Entry(HOBGOBLIN, count=2),
        Entry(EMP, count=100, location=Location.CARGO),
        name="Shield Buffer",
    )
    assert save([rifter], CATALOG) == (
        "%esf/1\n"
        'Rifter "Shield Buffer"\n'
        "\n"
        "2x 200mm AutoCannon II :Republic Fleet EMP S\n"
        "\n"
        "Medium Shield Extender II\n"
        "Warp Scrambler II !off\n"
        "\n"
        "Damage Control II\n"
        "\n"
        "2x Hobgoblin II\n"
        "\n"
        "100x Republic Fleet EMP S\n"
    )


def test_load_canonical():
    rifter = fit(Entry(AUTOCANNON), Entry(AUTOCANNON), Entry(EMP, location=Location.CARGO))
    assert load(save([rifter], CATALOG).encode(), CATALOG) == [
        fit(Entry(AUTOCANNON, count=2), Entry(EMP))
    ]


def test_load_str():
    assert load("%esf/1\nRifter\n", CATALOG) == [EsfFit(RIFTER)]


def test_mutaplasmid_rolls():
    entry = Entry(
        DAMAGE_CONTROL, mutaplasmid=DECAYED_DAMAGE_CONTROL_MUTAPLASMID, overrides={50: 31.5}
    )
    [loaded] = load(save([fit(entry)], CATALOG).encode(), CATALOG)
    assert loaded.entries[0].overrides == {50: 31.5, 974: 0.6, 975: 0.6, 976: 0.6, 977: 0.6}


def test_binary_round_trip():
    fits = [
        fit(Entry(SMALL_SECURE_CONTAINER, fit_name="Loot", location=Location.CARGO)),
        EsfFit(SMALL_SECURE_CONTAINER, "Loot", entries=[Entry(EMP, count=10)]),
    ]
    assert load(save_binary(fits, CATALOG), CATALOG) == load(save(fits, CATALOG).encode(), CATALOG)


@pytest.mark.parametrize(
    "rifter",
    [
        fit(Entry(None)),
        fit(Entry(AUTOCANNON, count=-1)),
        fit(Entry(999_999_999)),
        fit(Entry(AUTOCANNON, charge_count=10)),
        fit(Entry(DAMAGE_CONTROL, overrides={50: math.nan})),
        fit(Entry(AVATAR_UNPUBLISHED, location=Location.CARGO)),
        fit(Entry(RIFTER, fit_name="Shield Buffer"), name="Shield Buffer"),
        fit(name="Two\nlines"),
    ],
    ids=[
        "empty-slot-without-rack",
        "negative-count",
        "unknown-type",
        "charge-count-without-charge",
        "override-nan",
        "id-not-what-its-name-resolves-to",
        "fit-contains-itself",
        "name-with-newline",
    ],
)
def test_save_invalid(rifter: EsfFit):
    with pytest.raises(EsfError):
        save([rifter], CATALOG)


def test_shared_name_published_wins():
    assert save([fit(Entry(AVATAR, location=Location.CARGO))], CATALOG).endswith("Avatar\n")
