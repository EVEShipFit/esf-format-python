"""A Catalog read from the official SDE in JSONL."""

import json
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from esf_format import AttributeRecord, Kind, MutaplasmidRecord, TypeRecord, sde

_CATEGORY_SHIP = 6


@dataclass(frozen=True)
class _Named:
    id: int
    name: str
    published: bool


@dataclass(frozen=True)
class _Dogma:
    effects: list[int]
    squadron_size: int | None
    rollable: dict[int, float]


@dataclass(frozen=True)
class _Mutaplasmid:
    id: int
    bases: set[int]
    attributes: list[int]


def _rows(path: Path) -> Iterator[dict[str, Any]]:
    with open(path, encoding="utf-8") as f:
        for line in f:
            yield json.loads(line)


def _name_index(rows: list[_Named]) -> dict[str, int]:
    return sde.name_index(rows, lambda r: r.id, lambda r: r.name, lambda r: r.published)


class SdeJsonlCatalog:
    """A Catalog read from the official SDE in JSONL, unpacked into `directory`."""

    def __init__(self, directory: str | Path):
        directory = Path(directory)

        category_of_group = {g["_key"]: g["categoryID"] for g in _rows(directory / "groups.jsonl")}
        effect_category = {
            e["_key"]: e.get("effectCategoryID", 0) for e in _rows(directory / "dogmaEffects.jsonl")
        }

        mutaplasmid_rows = [
            _Mutaplasmid(
                m["_key"],
                {t for io in m["inputOutputMapping"] for t in io["applicableTypes"]},
                [a["_key"] for a in m["attributeIDs"]],
            )
            for m in _rows(directory / "dynamicItemAttributes.jsonl")
        ]
        rollable = {a for m in mutaplasmid_rows for a in m.attributes}

        dogma: dict[int, _Dogma] = {}
        for row in _rows(directory / "typeDogma.jsonl"):
            effects = [e["effectID"] for e in row.get("dogmaEffects", [])]
            values = {a["attributeID"]: a["value"] for a in row.get("dogmaAttributes", [])}
            dogma[row["_key"]] = _Dogma(
                effects,
                sde.squadron_size(values),
                {a: v for a, v in values.items() if a in rollable},
            )

        self._types: dict[int, TypeRecord] = {}
        type_rows: list[_Named] = []
        ships: list[_Named] = []
        for t in _rows(directory / "types.jsonl"):
            name = t.get("name", {}).get("en")
            if name is None:
                continue
            group_id = t["groupID"]
            category_id = category_of_group[group_id]
            d = dogma.get(t["_key"])
            effects = d.effects if d is not None else []
            self._types[t["_key"]] = TypeRecord(
                t["_key"],
                name,
                sde.kind(category_id, group_id, effects),
                sde.active({e: effect_category.get(e, 0) for e in effects}),
                float(t.get("capacity", 0)),
                float(t.get("volume", 0)),
                d.squadron_size if d is not None else None,
            )
            named = _Named(t["_key"], name, t.get("published", False))
            type_rows.append(named)
            if category_id == _CATEGORY_SHIP:
                ships.append(named)
        self._type_names = _name_index(type_rows)

        self._attributes: dict[int, AttributeRecord] = {}
        attribute_rows: list[_Named] = []
        defaults: dict[int, float] = {}
        for a in _rows(directory / "dogmaAttributes.jsonl"):
            self._attributes[a["_key"]] = AttributeRecord(a["_key"], a["name"])
            attribute_rows.append(_Named(a["_key"], a["name"], a.get("published", False)))
            defaults[a["_key"]] = float(a.get("defaultValue", 0))
        self._attribute_names = _name_index(attribute_rows)

        ship_names = _name_index(ships)
        self._modes: dict[int, list[TypeRecord]] = {}
        for mode in self._types.values():
            if mode.kind != Kind.MODE:
                continue
            hull = sde.mode_hull(mode.name, ship_names)
            if hull is not None:
                self._modes.setdefault(hull, []).append(mode)

        self._mutaplasmids: dict[int, list[MutaplasmidRecord]] = {}
        for m in sorted(mutaplasmid_rows, key=lambda m: m.id):
            for base in m.bases:
                d = dogma.get(base)
                values = d.rollable if d is not None else {}
                rolls = tuple((a, values.get(a, defaults.get(a, 0.0))) for a in m.attributes)
                record = MutaplasmidRecord(self._types[m.id], rolls)
                self._mutaplasmids.setdefault(base, []).append(record)

    def type(self, folded_name: str) -> TypeRecord | None:
        type_id = self._type_names.get(folded_name)
        return None if type_id is None else self._types.get(type_id)

    def type_by_id(self, type_id: int) -> TypeRecord | None:
        return self._types.get(type_id)

    def attribute(self, folded_name: str) -> AttributeRecord | None:
        attribute_id = self._attribute_names.get(folded_name)
        return None if attribute_id is None else self._attributes.get(attribute_id)

    def attribute_by_id(self, attribute_id: int) -> AttributeRecord | None:
        return self._attributes.get(attribute_id)

    def modes(self, hull_id: int) -> list[TypeRecord]:
        return self._modes.get(hull_id, [])

    def mutaplasmids(self, type_id: int) -> list[MutaplasmidRecord]:
        return self._mutaplasmids.get(type_id, [])
