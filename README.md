# esf-format

[![PyPI](https://img.shields.io/pypi/v/esf-format.svg)](https://pypi.org/project/esf-format/)
[![Python](https://img.shields.io/pypi/pyversions/esf-format.svg)](https://pypi.org/project/esf-format/)
[![CI](https://github.com/EVEShipFit/esf-format-python/actions/workflows/test.yml/badge.svg)](https://github.com/EVEShipFit/esf-format-python/actions/workflows/test.yml)

[![Discord](https://img.shields.io/badge/Discord-Join-5865F2?logo=discord&logoColor=white)](https://discord.gg/S5V5BkvNf7)

Read and write [esf/1](https://github.com/EVEShipFit/esf-format), the
plain-text format for EVE Online ship fits. Text, canonical and binary forms.
No dependencies.

```
pip install esf-format
```

## Usage

```python
import esf_format
from esf_format import Entry, EsfFit, Location, State

fit = EsfFit(
    hull=587,  # Rifter
    name="Shield Buffer",
    entries=[
        Entry(2889, count=3, charge=21898),  # 3 guns, a full load of ammo each
        Entry(None, location=Location.HIGH),  # an empty high slot
        Entry(448, state=State.OFF),  # an offline module
        Entry(2048),  # goes in its own rack
        Entry(2456, count=5),  # 5 drones
        Entry(21898, count=1000, location=Location.CARGO),
    ],
)

text = esf_format.save([fit], catalog)  # canonical text
data = esf_format.save_binary([fit], catalog)  # binary
fits = esf_format.load(data, catalog)  # text or binary

url = esf_format.to_base64url(data)  # the binary form in a URL
data = esf_format.from_base64url(url)
```

`save()` and `save_binary()` take entries in any order, and check every rule
of the spec. `load()` returns fits in canonical form. All three raise
`esf_format.EsfError` when a rule is broken. It says where: `line` for text,
or `fit` and `entry` (counting from 1) for fits.

## Fits

An `EsfFit` is one fit: `hull`, `name`, tactical `mode` and its `entries`.
`hull` is `None` for a fit without a ship. A document can hold more than one
fit.

Each `Entry` is one line of the fit. `None` means the default:

| field | what it is | `None` means |
| --- | --- | --- |
| `type` | The type ID. | An empty slot. |
| `count` | How many. | One; for fighters, a full squadron. |
| `fit_name` | The name of another fit in the list, which this ship or container carries. | Carries no fit. |
| `charge` | The charge loaded. | |
| `charge_count` | How many charges. | A full load. |
| `mutaplasmid` | The mutaplasmid applied. | |
| `overrides` | Attribute values by attribute ID. | |
| `state` | `State.OFF`, `ON` or `HEAT`. | Active if the type can be, else on. |
| `location` | `CARGO`, `BAY` or another hold; a rack, like `HIGH` or `TUBE`, for an empty slot or with `slot`. | Where the type goes by default. |
| `slot` | The slot in the `location` rack, counting from 1. `load()` never sets it: it returns the rack in slot order, with empty slots between. | The next free slot. |

## The Catalog

The library holds no game data. You give it a `Catalog`: an object that looks
up types and attributes in your copy of the SDE.

```python
class MyCatalog:
    def type(self, folded_name: str) -> esf_format.TypeRecord | None: ...
    def type_by_id(self, type_id: int) -> esf_format.TypeRecord | None: ...
    def attribute(self, folded_name: str) -> esf_format.AttributeRecord | None: ...
    def attribute_by_id(self, attribute_id: int) -> esf_format.AttributeRecord | None: ...

    # Optional. Without them, no hull has tactical modes and no type has mutaplasmids.
    def modes(self, hull_id: int) -> Sequence[esf_format.TypeRecord]: ...
    def mutaplasmids(self, type_id: int) -> Sequence[esf_format.MutaplasmidRecord]: ...
```

Each method and field says what to return and where in the SDE it comes
from. `esf_format.sde` has helpers for the parts that take more than a lookup:

```python
from esf_format import TypeRecord, sde

type_names = sde.name_index(
    types, lambda t: t["_key"], lambda t: t["name"]["en"], lambda t: t.get("published", False)
)

# effects: effectID -> effectCategoryID; attributes: attributeID -> value

TypeRecord(
    id=t["_key"],
    name=t["name"]["en"],
    kind=sde.kind(group["categoryID"], t["groupID"], effects.keys()),
    active=sde.active(effects),
    capacity=t.get("capacity", 0.0),
    volume=t.get("volume", 0.0),
    squadron_size=sde.squadron_size(attributes),
)
```

[examples/sde_jsonl_catalog.py](https://github.com/EVEShipFit/esf-format-python/blob/main/examples/sde_jsonl_catalog.py)
is a complete example on the official SDE in JSONL: copy it into your project.

## ESI

ESI gives each item in a ship a `location_flag`. `esf_format.esi` turns it
into a location and a slot:

```python
from esf_format import Entry, Location, esi

Entry(type_id, location=esi.location(flag) or Location.CARGO, slot=esi.slot(flag))
```

`HiSlot2` gives `HIGH` and slot 3, and `ShipHangar` gives `MAINTENANCE`.
A flag that is not inside a ship, like `Hangar`, gives None; the example puts
those items in the cargo hold.

Only a ship, structure or container can be a fit's hull. Check
`(t := catalog.type_by_id(type_id)) is not None and t.kind.can_be_hull` before
you use a type as one.

## Tests

The test cases live in [esf-format](https://github.com/EVEShipFit/esf-format):

```
git clone --branch v1.0 https://github.com/EVEShipFit/esf-format
uv sync
uv run --project esf-format/tools esf-test -- .venv/bin/python tests/program.py
uv run pytest
```
