"""What esf/1 needs to know about types and attributes (SPEC §5, §6)."""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction
from typing import Protocol


class Kind(StrEnum):
    """What a type is, which decides where it goes in a fit (esf/1 spec §5).

    Check the group rules first (MODE, CONTAINER, BOOSTER), then the category rules.
    `esf_format.sde.kind()` works this out from the SDE for you.
    """

    HULL = "hull"
    """A ship or a structure: SDE category `Ship` (6) or `Structure` (65)."""

    CONTAINER = "container"
    """A container that can carry another fit, like a Small Secure Container.

    SDE group `Cargo Container` (12), `Secure Cargo Container` (340),
    `Audit Log Secure Container` (448) or `Freight Container` (649).
    """

    MODE = "mode"
    """A tactical mode, like the Hecate's Sharpshooter Mode: SDE group `Ship Modifiers` (1306)."""

    SUB = "sub"
    """A subsystem, like on a Tengu: SDE category `Subsystem` (32)."""

    HIGH = "high"
    """A high slot module, like a gun.

    SDE category `Module` (7) or `Structure Module` (66), with effect `hiPower` (12).
    """

    MID = "mid"
    """A mid slot module, like a shield extender.

    Category `Module` or `Structure Module`, with effect `medPower` (13).
    """

    LOW = "low"
    """A low slot module, like a damage control.

    Category `Module` or `Structure Module`, with effect `loPower` (11).
    """

    RIG = "rig"
    """A rig: category `Module` or `Structure Module`, with effect `rigSlot` (2663)."""

    SVC = "svc"
    """A structure service module.

    Category `Module` or `Structure Module`, with effect `serviceSlot` (6306).
    """

    DRONE = "drone"
    """A drone: SDE category `Drone` (18)."""

    FIGHTER = "fighter"
    """A fighter: SDE category `Fighter` (87)."""

    CHARGE = "charge"
    """Ammunition, a script or anything else loaded into a module: SDE category `Charge` (8)."""

    IMPLANT = "implant"
    """An implant: SDE category `Implant` (20), except the boosters in it."""

    BOOSTER = "booster"
    """A booster, also called a drug: SDE group `Booster` (303), inside category `Implant`."""

    OTHER = "other"
    """Anything else, like ore or a module without a slot. It goes in the cargo."""


@dataclass(frozen=True)
class TypeRecord:
    """One type, like "Rifter" or "200mm AutoCannon II", as the library needs it.

    With the SDE, most fields come from `types.jsonl`. `kind`, `active` and `squadron_size`
    also need `groups.jsonl`, `typeDogma.jsonl` and `dogmaEffects.jsonl`, through the
    helpers in `esf_format.sde`. Include every type in `types.jsonl`. A type with no row
    in `typeDogma.jsonl` has no effects and no attributes: give the helpers an empty
    list or dict.
    """

    id: int
    """The type ID, like 587 for the Rifter. In the SDE this is `_key`."""

    name: str
    """The English name, like "Rifter". In the SDE this is `name.en`."""

    kind: Kind
    """What it is, which decides where it goes in a fit. Use `esf_format.sde.kind()`."""

    active: bool
    """Whether the type runs when it is turned on, like a gun or a shield booster.

    A plate or a damage control only goes online, so it is False.
    Use `esf_format.sde.active()` to work this out from the type's effects.
    """

    capacity: float
    """How much the type holds, in m³; for a module, how much ammunition fits in it.

    In the SDE this is `capacity`. Use 0 when the type has none.
    """

    volume: float
    """How much room one of it takes, in m³. In the SDE this is `volume`.

    Use 0 when the type has none.
    """

    squadron_size: int | None = None
    """For a fighter, how many make up a full squadron. None for anything else.

    In the SDE this is the attribute `fighterSquadronMaxSize`;
    `esf_format.sde.squadron_size()` reads it for you.
    """


@dataclass(frozen=True)
class AttributeRecord:
    """One dogma attribute, like "speedFactor", as the library needs it.

    With the SDE, both fields come from `dogmaAttributes.jsonl`.
    """

    id: int
    """The attribute ID, like 20 for speedFactor. In the SDE this is `_key`."""

    name: str
    """The name, like "speedFactor". In the SDE this is `name`; it is not translated."""


@dataclass(frozen=True)
class MutaplasmidRecord:
    """One mutaplasmid that can be applied to a base type.

    For example "Unstable 5MN Microwarpdrive Mutaplasmid". With the SDE, these come from
    `dynamicItemAttributes.jsonl`. Each entry there is one mutaplasmid. Its
    `inputOutputMapping` is a list; the base types it applies to are all the
    `applicableTypes` across that list.
    """

    type: TypeRecord
    """The mutaplasmid's own type: the type whose ID is the entry's `_key`."""

    rolls: tuple[tuple[int, float], ...]
    """The attributes the mutaplasmid changes, each with the base type's value before the change.

    Each pair is an attribute ID and a value. The attribute IDs are the `_key` of each
    item in the entry's `attributeIDs`; its `min` and `max` are not needed. Each value is
    the base type's value of that attribute in `typeDogma.jsonl`. When the base type does
    not have it, use the attribute's `defaultValue` in `dogmaAttributes.jsonl`, or 0 when
    that is missing too.
    """


class Catalog(Protocol):
    """Where the library looks up game data. You write this, on top of your copy of the SDE.

    The library holds no game data itself. Whenever it meets a name or an ID in a fit,
    it asks the catalog what that is. `esf_format.sde` has helpers for the parts that
    take more than a lookup. For tactical modes and mutaplasmids, see `ModeCatalog` and
    `MutaplasmidCatalog`.

    The `§` numbers point to sections of the esf/1 spec:
    https://github.com/EVEShipFit/esf-format/blob/main/SPEC.md
    """

    def type(self, folded_name: str) -> TypeRecord | None:
        """Finds a type by its name.

        The name comes from a fit, so a user may have typed it in any case.
        The library already case-folded it with `esf_format.fold()`, so "Rifter",
        "RIFTER" and "rifter" all reach you as "rifter". Case folding is like lowercase,
        but gives the same result in every language, so use `esf_format.fold()`, not
        `str.lower()` or `str.casefold()`. Store your type names the same way, by calling
        `esf_format.fold()` on each one, and look this name up in that store.

        Include unpublished types too. Some names belong to more than one type.
        Then return the published one; if that is still more than one, the lowest ID.
        `esf_format.sde.name_index()` builds this store for you.

        Return None if no type has this name.
        """
        ...

    def type_by_id(self, type_id: int) -> TypeRecord | None:
        """Finds a type by its ID. Return None if there is no type with this ID."""
        ...

    def attribute(self, folded_name: str) -> AttributeRecord | None:
        """Finds an attribute by its name, like "speedfactor".

        This works the same way as `type()`: the name is already case-folded with
        `esf_format.fold()`, unpublished attributes count too, and where names are shared,
        the published one wins, then the lowest ID. `esf_format.sde.name_index()` builds
        this store for you.

        Return None if no attribute has this name.
        """
        ...

    def attribute_by_id(self, attribute_id: int) -> AttributeRecord | None:
        """Finds an attribute by its ID. Return None if there is no attribute with this ID."""
        ...


class ModeCatalog(Catalog, Protocol):
    """A Catalog that also knows tactical modes.

    The `modes()` method is optional. Leave it out and no hull has tactical modes.
    """

    def modes(self, hull_id: int) -> Sequence[TypeRecord]:
        """The tactical modes a hull can be in.

        For example the Hecate's Defense, Propulsion and Sharpshooter Mode. Return an
        empty list for a hull without tactical modes. In the SDE, modes are the types of
        kind `Kind.MODE`; `esf_format.sde.mode_hull()` tells you which hull each one
        belongs to.
        """
        ...


class MutaplasmidCatalog(Catalog, Protocol):
    """A Catalog that also knows mutaplasmids.

    The `mutaplasmids()` method is optional. Leave it out and no type has mutaplasmids.
    """

    def mutaplasmids(self, type_id: int) -> Sequence[MutaplasmidRecord]:
        """The mutaplasmids that can be applied to a type.

        See `MutaplasmidRecord` for where they come from. Return an empty list for a type
        no mutaplasmid applies to.
        """
        ...


def modes_of(catalog: Catalog, hull: TypeRecord) -> Sequence[TypeRecord]:
    modes = getattr(catalog, "modes", None)
    return () if modes is None else modes(hull.id)


def mutaplasmids_of(catalog: Catalog, base: TypeRecord) -> Sequence[MutaplasmidRecord]:
    mutaplasmids = getattr(catalog, "mutaplasmids", None)
    return () if mutaplasmids is None else mutaplasmids(base.id)


def attribute_of(catalog: Catalog, attribute_id: int) -> AttributeRecord:
    attribute = catalog.attribute_by_id(attribute_id)
    if attribute is None:
        raise LookupError(f"the catalog has no attribute {attribute_id}")
    return attribute


def full_load(item: TypeRecord, charge: TypeRecord) -> int | None:
    """How many charges fit in an item (§6.5)."""
    if item.capacity <= 0 or charge.volume <= 0:
        return None
    return int(Fraction(str(item.capacity)) / Fraction(str(charge.volume)))
