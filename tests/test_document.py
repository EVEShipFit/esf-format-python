import base64
import os
import tomllib
from pathlib import Path

import pytest
from test_api import CATALOG, RIFTER

from esf_format import (
    BinaryExtra,
    Document,
    EsfFit,
    EsfFormatError,
    TextExtra,
    binary_field,
    from_base64url,
    load,
    load_document,
    save,
    save_binary,
)

VALID = Path(os.environ.get("ESF_TESTS", "esf-format/tests")) / "valid"


def _input(case: Path) -> bytes:
    if (case / "input.b64").exists():
        return from_base64url((case / "input.b64").read_text())
    return (case / "input.esf").read_bytes()


def _expected(case: Path) -> list[TextExtra | BinaryExtra]:
    path = case / "extra.toml"
    if not path.exists():
        return []
    out: list[TextExtra | BinaryExtra] = []
    for e in tomllib.loads(path.read_text())["extra"]:
        if "field" in e:
            raw = e["bytes"]
            out.append(
                BinaryExtra(e["field"], base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
            )
        else:
            out.append(TextExtra(e["name"], e["version"], e["text"]))
    return out


@pytest.mark.parametrize("case", sorted(VALID.iterdir()), ids=lambda p: p.name)
def test_valid_cases(case: Path) -> None:
    data = _input(case)
    document = load_document(data, CATALOG)
    assert document.extra == _expected(case)
    assert document.fits == load(data, CATALOG)


def test_cases_with_extra_exist() -> None:
    assert sum(1 for c in VALID.iterdir() if (c / "extra.toml").exists()) >= 4


def test_text_extra() -> None:
    data = "%a/1\r\nx\r\n%esf/1\nRifter\n%b/22\n\n\n%c/3\n%d/0"
    document = load_document(data, CATALOG)
    assert document.extra == [
        TextExtra("a", 1, "x\r\n"),
        TextExtra("b", 22, "\n\n"),
        TextExtra("c", 3, ""),
        TextExtra("d", 0, ""),
    ]
    assert document.fits == load(data, CATALOG)


def test_text_extra_unicode() -> None:
    document = load_document("%esf/1\nRifter\n%x/1\nŝ €\n".encode(), CATALOG)
    assert document.extra == [TextExtra("x", 1, "ŝ €\n")]


def test_no_extra() -> None:
    fits = [EsfFit(RIFTER)]
    assert load_document(save(fits, CATALOG), CATALOG) == Document(
        load(save(fits, CATALOG), CATALOG)
    )
    assert load_document(save_binary(fits, CATALOG), CATALOG).extra == []


def test_unknown_esf_version() -> None:
    with pytest.raises(EsfFormatError):
        load_document("%esf/1\nRifter\n%esf/2\nRifter\n", CATALOG)


@pytest.mark.parametrize("version", ["4294967296", "9" * 5000])
def test_text_extra_version_too_large(version: str) -> None:
    with pytest.raises(EsfFormatError):
        load_document(f"%esf/1\nRifter\n%x/{version}\n", CATALOG)


def test_load_skips_version_too_large() -> None:
    data = "%esf/1\nRifter\n%fleet/99999999999\n"
    assert load(data, CATALOG) == [EsfFit(RIFTER)]
    with pytest.raises(EsfFormatError):
        load_document(data, CATALOG)


def test_text_extra_version_max() -> None:
    document = load_document("%esf/1\nRifter\n%x/0004294967295\n", CATALOG)
    assert document.extra == [TextExtra("x", 4294967295, "")]


def test_binary_field_round_trip() -> None:
    fits = [EsfFit(RIFTER)]
    data = save_binary(fits, CATALOG) + binary_field(2, b"\x01\x02") + binary_field(1000, b"")
    document = load_document(data, CATALOG)
    assert document.fits == load(save_binary(fits, CATALOG), CATALOG)
    assert document.extra == [BinaryExtra(2, b"\x01\x02"), BinaryExtra(1000, b"")]


def test_binary_field_before_fits() -> None:
    data = binary_field(536870911, b"x") + save_binary([EsfFit(RIFTER)], CATALOG)
    document = load_document(data, CATALOG)
    assert document.extra == [BinaryExtra(536870911, b"x")]
    assert document.fits[0].hull == RIFTER


def test_binary_skips_other_wire_types() -> None:
    varint = bytes([2 << 3 | 0, 5])
    fixed64 = bytes([3 << 3 | 1]) + bytes(8)
    fixed32 = bytes([4 << 3 | 5]) + bytes(4)
    group = bytes([5 << 3 | 3]) + binary_field(6, b"in") + bytes([5 << 3 | 4])
    data = save_binary([EsfFit(RIFTER)], CATALOG) + varint + fixed64 + fixed32 + group
    assert load_document(data, CATALOG).extra == []


@pytest.mark.parametrize("field", [-1, 0, 1, 536870912])
def test_binary_field_rejects(field: int) -> None:
    with pytest.raises(ValueError):
        binary_field(field, b"")


def test_binary_field_takes_bytes_like() -> None:
    assert binary_field(2, bytearray(b"ab")) == b"\x12\x02ab"
    with pytest.raises(TypeError):
        binary_field(2, 5)  # type: ignore[arg-type]
