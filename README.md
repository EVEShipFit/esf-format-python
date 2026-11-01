# esf-format

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
fits = esf_format.load(data, catalog)  # text or binary, as bytes
```

`save()` and `save_binary()` take entries in any order, and check every rule
of the spec. `load()` returns fits in canonical form. All three raise
`esf_format.EsfError` when a rule is broken.

## Fits

An `EsfFit` is one fit: `hull`, `name`, tactical `mode` and its `entries`.
`hull` is `None` for a fit without a ship. A document can hold more than one
fit.

Each `Entry` is one line of the fit. `None` means the default:

| field | what it is | `None` means |
| --- | --- | --- |
| `type` | The type ID. | An empty slot. |
| `count` | How many. | One; for fighters, a full squadron. |
| `fit_name` | The name of another fit in the list, which this ship or container carries. | |
| `charge` | The charge loaded. | |
| `charge_count` | How many charges. | A full load. |
| `mutaplasmid` | The mutaplasmid applied. | |
| `overrides` | Attribute values by attribute ID. | |
| `state` | `State.OFF`, `ON` or `HEAT`. | Active if the type can be, else on. |
| `location` | A rack, `CARGO`, `BAY` or another hold. | Where the type goes by default. |

## The Catalog

The library holds no game data. You give it a `Catalog`: an object that looks
up types and attributes in your copy of the SDE.

```python
class MyCatalog:
    def type(self, folded: str) -> esf_format.TypeRecord | None: ...
    def type_by_id(self, type_id: int) -> esf_format.TypeRecord | None: ...
    def attribute(self, folded: str) -> esf_format.AttributeRecord | None: ...
    def attribute_by_id(self, attribute_id: int) -> esf_format.AttributeRecord | None: ...

    # Optional; needed only for fits with a tactical mode or a mutaplasmid.
    def modes(self, hull_id: int) -> list[esf_format.TypeRecord]: ...
    def mutaplasmids(self, type_id: int) -> list[esf_format.MutaplasmidRecord]: ...
```

Names are looked up folded: index them with `esf_format.fold(name)`. Where
names are shared, published wins, then the lowest ID (§4.2).
[tests/catalog.py](tests/catalog.py) is a complete example.

## Tests

The test cases live in [esf-format](https://github.com/EVEShipFit/esf-format):

```
git clone https://github.com/EVEShipFit/esf-format
uv sync
uv run --project esf-format/tools esf-test -- .venv/bin/python tests/program.py
uv run pytest
```
