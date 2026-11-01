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


def _method(catalog: Catalog, name: str):
    method = getattr(catalog, name, None)
    if method is None:
        raise NotImplementedError(f"the catalog has no {name}()")
    return method


def modes_of(catalog: Catalog, hull: TypeRecord) -> Sequence[TypeRecord]:
    return _method(catalog, "modes")(hull.id)


def mutaplasmids_of(catalog: Catalog, base: TypeRecord) -> Sequence[MutaplasmidRecord]:
    return _method(catalog, "mutaplasmids")(base.id)


def full_load(item: TypeRecord, charge: TypeRecord) -> int | None:
    """How many charges fit in an item (§6.5)."""
    if item.capacity <= 0 or charge.volume <= 0:
        return None
    return int(Fraction(str(item.capacity)) / Fraction(str(charge.volume)))
