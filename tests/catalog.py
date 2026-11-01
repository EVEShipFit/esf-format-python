"""A Catalog read from the esf-format test catalog."""

import json

from esf_format import AttributeRecord, Kind, MutaplasmidRecord, TypeRecord, fold


def _by_name(entries: list[dict]) -> dict[str, int]:
    index = {}
    for e in sorted(entries, key=lambda e: (not e["published"], e["id"])):
        index.setdefault(fold(e["name"]), e["id"])
    return index


class JsonCatalog:
    def __init__(self, path: str):
        with open(path) as f:
            data = json.load(f)
        self._types = {
            t["id"]: TypeRecord(
                t["id"],
                t["name"],
                Kind(t["kind"]),
                t["active"],
                t["capacity"],
                t["volume"],
                t.get("squadron_size"),
            )
            for t in data["types"]
        }
        self._attributes = {
            a["id"]: AttributeRecord(a["id"], a["name"]) for a in data["attributes"]
        }
        self._type_names = _by_name(data["types"])
        self._attribute_names = _by_name(data["attributes"])
        self._modes = {m["hull"]: [self._types[t] for t in m["modes"]] for m in data["modes"]}
        self._mutaplasmids: dict[int, list[MutaplasmidRecord]] = {}
        for m in data["mutaplasmids"]:
            rolls = tuple(map(tuple, m["rolls"]))
            record = MutaplasmidRecord(self._types[m["mutaplasmid"]], rolls)
            self._mutaplasmids.setdefault(m["base"], []).append(record)

    def type(self, folded: str) -> TypeRecord | None:
        return self._types.get(self._type_names.get(folded))

    def type_by_id(self, type_id: int) -> TypeRecord | None:
        return self._types.get(type_id)

    def attribute(self, folded: str) -> AttributeRecord | None:
        return self._attributes.get(self._attribute_names.get(folded))

    def attribute_by_id(self, attribute_id: int) -> AttributeRecord | None:
        return self._attributes.get(attribute_id)

    def modes(self, hull_id: int) -> list[TypeRecord]:
        return self._modes.get(hull_id, [])

    def mutaplasmids(self, type_id: int) -> list[MutaplasmidRecord]:
        return self._mutaplasmids.get(type_id, [])
