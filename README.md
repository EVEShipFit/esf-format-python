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

fits = esf_format.read(data, catalog)  # text or binary, as bytes
text = esf_format.to_text(fits)  # canonical text form
binary = esf_format.to_binary(fits)  # binary form
```

`read()` raises `esf_format.EsfError` for an invalid document.

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
```
