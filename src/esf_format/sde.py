"""Helpers to build a Catalog from the SDE (SPEC §4.2, §5, §6.1, §6.4).

These cover the fields that take more than a lookup. Each helper takes plain values
from the SDE files, so it works however you load them.
"""

from collections.abc import Callable, Iterable, Mapping
from typing import TypeVar

from .catalog import Kind
from .names import fold

_T = TypeVar("_T")

_CATEGORY_KINDS = {
    6: Kind.HULL,
    65: Kind.HULL,
    32: Kind.SUB,
    18: Kind.DRONE,
    87: Kind.FIGHTER,
    8: Kind.CHARGE,
    20: Kind.IMPLANT,
}
_CATEGORY_MODULES = (7, 66)

_GROUP_BOOSTER = 303
_GROUP_SHIP_MODIFIERS = 1306
_GROUP_CONTAINERS = (12, 340, 448, 649)

_EFFECT_ONLINE = 16
_EFFECT_CATEGORIES_RUNNING = (1, 2)
_SLOT_EFFECTS = {12: Kind.HIGH, 13: Kind.MID, 11: Kind.LOW, 2663: Kind.RIG, 6306: Kind.SVC}

_ATTRIBUTE_SQUADRON_SIZE = 2215


def kind(category_id: int, group_id: int, effect_ids: Iterable[int]) -> Kind:
    """Works out what a type is. See `Kind` for each rule.

    `category_id` is the `categoryID` of the type's group, in `groups.jsonl`.
    `group_id` is the type's `groupID`, in `types.jsonl`.
    `effect_ids` are the `effectID`s in the type's `dogmaEffects`, in `typeDogma.jsonl`.

    For example, `kind(7, 55, [16, 12, 34])` is `Kind.HIGH` for a 200mm AutoCannon II.
    """
    if group_id == _GROUP_SHIP_MODIFIERS:
        return Kind.MODE
    if group_id in _GROUP_CONTAINERS:
        return Kind.CONTAINER
    if group_id == _GROUP_BOOSTER:
        return Kind.BOOSTER
    if category_id in _CATEGORY_MODULES:
        return next((_SLOT_EFFECTS[e] for e in effect_ids if e in _SLOT_EFFECTS), Kind.OTHER)
    return _CATEGORY_KINDS.get(category_id, Kind.OTHER)


def active(effects: Mapping[int, int]) -> bool:
    """Works out whether a type runs when it is turned on (§6.4), for `TypeRecord.active`.

    `effects` maps each `effectID` in the type's `dogmaEffects` (in `typeDogma.jsonl`)
    to that effect's `effectCategoryID` (in `dogmaEffects.jsonl`).

    A type runs when one of its effects is in category 1 (active) or 2 (target).
    The SDE puts the `online` effect in category 1 too, but going online is not
    running, so that one does not count.
    """
    return any(
        effect_id != _EFFECT_ONLINE and category in _EFFECT_CATEGORIES_RUNNING
        for effect_id, category in effects.items()
    )


def squadron_size(attributes: Mapping[int, float]) -> int | None:
    """Reads how many fighters make up a full squadron, for `TypeRecord.squadron_size`.

    `attributes` maps each `attributeID` in the type's `dogmaAttributes`
    (in `typeDogma.jsonl`) to its `value`. Returns None when the type has no
    `fighterSquadronMaxSize` (2215), which only fighters have.
    """
    value = attributes.get(_ATTRIBUTE_SQUADRON_SIZE)
    return None if value is None else int(value)


def mode_hull(mode_name: str, ship_names: Mapping[str, int]) -> int | None:
    """Finds which hull a tactical mode belongs to, for `ModeCatalog.modes()`.

    The SDE does not link a mode to its hull. Instead, a mode's name starts with
    its hull's name: "Hecate Sharpshooter Mode" belongs to the Hecate. This tries
    the longest start of `mode_name` first, a whole word at a time.

    `ship_names` is a `name_index()` of every type in category `Ship` (6).
    Returns the hull's type ID, or None when no ship name matches.
    """
    words = mode_name.split(" ")
    for n in range(len(words) - 1, 0, -1):
        hull = ship_names.get(fold(" ".join(words[:n])))
        if hull is not None:
            return hull
    return None


def name_index(
    entries: Iterable[_T],
    id: Callable[[_T], int],
    name: Callable[[_T], str],
    published: Callable[[_T], bool],
) -> dict[str, int]:
    """Builds the name store that `Catalog.type()` and `Catalog.attribute()` look names up in.

    Give it every type, or every attribute, including unpublished ones, and a function
    for each of its ID, name and whether it is published. Each name is case-folded with
    `esf_format.fold()`, the same way the library does with the names in a fit. Where
    names are shared, the published one wins, then the lowest ID (§4.2). In the SDE, a
    type or attribute without `published` counts as not published.

    Returns a dict from case-folded name to ID. For example, with the rows of
    `types.jsonl`::

        name_index(
            rows,
            lambda t: t["_key"],
            lambda t: t["name"]["en"],
            lambda t: t.get("published", False),
        )
    """
    index: dict[str, int] = {}
    for e in sorted(entries, key=lambda e: (not published(e), id(e))):
        index.setdefault(fold(name(e)), id(e))
    return index
