import math
import os

import pytest
from catalog import JsonCatalog

from esf_format import (
    Entry,
    EsfError,
    EsfFit,
    Location,
    State,
    from_base64url,
    is_text,
    load,
    save,
    save_binary,
    to_base64url,
)

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
    ("fits", "message"),
    [
        pytest.param([], "at least one fit", id="no-fits"),
        pytest.param([fit(Entry(None))], "an empty slot must name its rack", id="empty-no-rack"),
        pytest.param([fit(Entry(AUTOCANNON, count=-1))], "at least 1", id="negative-count"),
        pytest.param([fit(Entry(999_999_999))], "unknown item type ID", id="unknown-type"),
        pytest.param(
            [fit(Entry(AUTOCANNON, location=Location.HIGH))],
            "only for an empty slot",
            id="rack-on-item",
        ),
        pytest.param(
            [fit(Entry(AUTOCANNON, charge_count=10))], "without a charge", id="charge-count-alone"
        ),
        pytest.param(
            [fit(Entry(DAMAGE_CONTROL, overrides={50: math.nan}))], "not finite", id="override-nan"
        ),
        pytest.param(
            [fit(Entry(DAMAGE_CONTROL, overrides={50: 10**400}))], "not finite", id="override-huge"
        ),
        pytest.param(
            [fit(Entry(AVATAR_UNPUBLISHED, location=Location.CARGO))],
            "not what its name resolves to",
            id="id-shadowed",
        ),
        pytest.param(
            [fit(Entry(RIFTER, fit_name="Buffer"), name="Buffer")],
            "cannot contain itself",
            id="contains-itself",
        ),
        pytest.param([fit(name="Two\nlines")], "CR or LF", id="name-newline"),
    ],
)
def test_save_invalid(fits: list[EsfFit], message: str):
    with pytest.raises(EsfError, match=message):
        save(fits, CATALOG)


def test_error_location():
    with pytest.raises(EsfError) as error:
        save([fit(), fit(Entry(AUTOCANNON), Entry(999_999_999))], CATALOG)
    assert (error.value.fit, error.value.entry, error.value.line) == (2, 2, None)
    assert str(error.value).startswith("fit 2, entry 2: ")


def test_empty_name_is_no_name():
    assert save([fit(name="")], CATALOG) == "%esf/1\nRifter\n"


def test_shared_name_published_wins():
    assert save([fit(Entry(AVATAR, location=Location.CARGO))], CATALOG).endswith("Avatar\n")


@pytest.mark.parametrize(
    ("data", "message"),
    [
        pytest.param(b"", "the document is empty", id="empty"),
        pytest.param("%esf/1\nRifter\ud800\n", "not valid UTF-8", id="lone-surrogate"),
        pytest.param(b"\x10\x01", "at least one fit", id="binary-without-fits"),
        pytest.param(
            "%esf/1\nRifter\n4294967295x Damage Control II\n4294967295x Damage Control II\n",
            "too large",
            id="merged-count-too-large",
        ),
    ],
)
def test_load_invalid(data: bytes | str, message: str):
    with pytest.raises(EsfError, match=message):
        load(data, CATALOG)


class MinimalCatalog:
    def __init__(self, catalog: JsonCatalog):
        self.type = catalog.type
        self.type_by_id = catalog.type_by_id
        self.attribute = catalog.attribute
        self.attribute_by_id = catalog.attribute_by_id


@pytest.mark.parametrize(
    ("line", "message"),
    [
        ("Hecate /Defense", "no tactical modes"),
        ("Rifter\nDamage Control II +Decayed", "no mutaplasmid"),
    ],
    ids=["mode", "mutaplasmid"],
)
def test_catalog_without_optional_methods(line: str, message: str):
    with pytest.raises(EsfError, match=message):
        load(f"%esf/1\n{line}\n", MinimalCatalog(CATALOG))


def test_base64url():
    data = save_binary([fit(Entry(AUTOCANNON))], CATALOG)
    url = to_base64url(data)
    assert "=" not in url
    assert from_base64url(url) == data
    with pytest.raises(EsfError):
        from_base64url("not base64url!")


def test_is_text():
    assert is_text("%esf/1\n") and is_text(b"%esf/1\n")
    assert not is_text(b"\x0a\x02")


class CatalogWithoutRollAttributes(MinimalCatalog):
    def __init__(self, catalog: JsonCatalog):
        super().__init__(catalog)
        self.mutaplasmids = catalog.mutaplasmids
        self.attribute_by_id = lambda attribute_id: None


def test_catalog_missing_roll_attribute():
    with pytest.raises(LookupError, match="no attribute"):
        load("%esf/1\nRifter\nDamage Control II +Decayed\n", CatalogWithoutRollAttributes(CATALOG))
