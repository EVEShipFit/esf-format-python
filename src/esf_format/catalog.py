"""What esf/1 needs to know about types and attributes (SPEC §5, §6)."""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import StrEnum
from fractions import Fraction
from typing import Protocol


class Kind(StrEnum):
    """What a type is (§5)."""

    HULL = "hull"
    CONTAINER = "container"
    MODE = "mode"
    SUB = "sub"
    HIGH = "high"
    MID = "mid"
    LOW = "low"
    RIG = "rig"
    SVC = "svc"
    DRONE = "drone"
    FIGHTER = "fighter"
    CHARGE = "charge"
    IMPLANT = "implant"
    BOOSTER = "booster"
    OTHER = "other"


@dataclass(frozen=True)
class TypeRecord:
    id: int
    name: str
    kind: Kind
    active: bool
    capacity: float
    volume: float
    squadron_size: int | None = None


@dataclass(frozen=True)
class AttributeRecord:
    id: int
    name: str


@dataclass(frozen=True)
class MutaplasmidRecord:
    type: TypeRecord
    rolls: tuple[tuple[int, float], ...]


class Catalog(Protocol):
    """Types and attributes, by folded name (§6.10) or by ID."""

    def type(self, folded: str) -> TypeRecord | None: ...

    def type_by_id(self, type_id: int) -> TypeRecord | None: ...

    def attribute(self, folded: str) -> AttributeRecord | None: ...

    def attribute_by_id(self, attribute_id: int) -> AttributeRecord | None: ...


class ModeCatalog(Catalog, Protocol):
    def modes(self, hull_id: int) -> Sequence[TypeRecord]: ...


class MutaplasmidCatalog(Catalog, Protocol):
    def mutaplasmids(self, type_id: int) -> Sequence[MutaplasmidRecord]: ...


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
