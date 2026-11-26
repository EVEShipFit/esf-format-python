"""Reading the text form into lines, without a Catalog (SPEC §4.1, grammar.ebnf)."""

import re
from dataclasses import dataclass, field
from typing import NamedTuple, NoReturn

from .errors import EsfFormatError
from .model import TextExtra

SIGILS = frozenset(':+{!@/"')
RACKS = ("sub", "high", "mid", "low", "rig", "svc")
TUBE = "tube"
PINNABLE = (*RACKS, TUBE)
HOLDS = (
    "ammo",
    "booster",
    "command",
    "corpse",
    "depot",
    "expedition",
    "fleet",
    "frigate",
    "fuel",
    "gas",
    "ice",
    "infrastructure",
    "maintenance",
    "mineral",
    "mining",
    "moon",
    "planetary",
    "quafe",
    "subsystem",
)
STORED = ("cargo", "bay", *HOLDS)

UINT32_MAX = 0xFFFFFFFF

_COUNT = re.compile(r"[0-9]+x")
_TYPE_ID = re.compile(r"#([0-9]+)")
_NAME_WITH_ID = re.compile(r"(.*[^ ])#([0-9]+)")
_QUOTED = re.compile(r'"((?:[^"]|"")*+)"')
_HEADER = re.compile(r" *%([a-z][a-z0-9-]*)/([0-9]+) *")
_STATE = re.compile(r"!(off|on|heat)")
_LOCATION = re.compile(r"@([a-z]+)([0-9]*)")
_OVERRIDE = re.compile(r"([A-Za-z][A-Za-z0-9]*) +(-?[0-9]+(?:\.[0-9]+)?)")


class TypeRef(NamedTuple):
    name: str
    id: int | None = None


@dataclass
class EmptyLine:
    number: int
    rack: str
    count: int | None = None
    index: int | None = None


@dataclass
class ItemLine:
    number: int
    type: TypeRef
    count: int | None = None
    fit_name: str | None = None
    charge: TypeRef | None = None
    charge_count: int | None = None
    mutaplasmid: str | None = None
    overrides: list[tuple[str, str]] = field(default_factory=list)
    state: str | None = None
    location: str | None = None
    index: int | None = None


@dataclass
class FitBlock:
    number: int
    hull_line: int
    hull: TypeRef | None = None
    fit_name: str | None = None
    mode: str | None = None
    lines: list[EmptyLine | ItemLine] = field(default_factory=list)


def is_count(token: str) -> bool:
    return _COUNT.fullmatch(token) is not None


def ends_in_type_id(name: str) -> bool:
    return _NAME_WITH_ID.fullmatch(name) is not None


class _Cursor:
    def __init__(self, number: int, text: str):
        self.number = number
        self.s = text
        self.i = 0

    def error(self, message: str) -> NoReturn:
        raise EsfFormatError(message, self.number)

    def peek(self) -> str:
        return self.s[self.i] if self.i < len(self.s) else ""

    def token(self) -> str:
        end = self.s.find(" ", self.i)
        return self.s[self.i : end if end >= 0 else len(self.s)]

    def skip_spaces(self) -> bool:
        start = self.i
        while self.peek() == " ":
            self.i += 1
        return self.i > start

    def next_element(self) -> bool:
        """Step over the separating space; False at the end of the line or a comment."""
        spaced = self.skip_spaces()
        if self.i >= len(self.s):
            return False
        if self.s.startswith("//", self.i):
            if not spaced:
                self.error("a comment needs a space before it")
            self.i = len(self.s)
            return False
        if not spaced:
            self.error(f"expected a space before {self.token()!r}")
        return True

    def positive(self, digits: str, what: str) -> int:
        digits = digits.lstrip("0")
        if not digits:
            self.error(f"{what} must be at least 1")
        if len(digits) > 10 or int(digits) > UINT32_MAX:
            self.error(f"{what} is too large")
        return int(digits)

    def finish(self) -> None:
        if self.next_element():
            self.error(f"unexpected {self.token()!r}")

    def count(self) -> int | None:
        token = self.token()
        if not is_count(token):
            return None
        self.i += len(token)
        if not self.next_element():
            self.error("a count must be followed by a type name")
        return self.positive(token[:-1], "a count")

    def quoted(self) -> str:
        match = _QUOTED.match(self.s, self.i)
        if not match:
            self.error("unterminated quoted string")
        if not match.group(1):
            self.error("a quoted string cannot be empty")
        self.i = match.end()
        return match.group(1).replace('""', '"')

    def word(self) -> str:
        token = self.token()
        self.i += len(token)
        return token

    def type_name(self) -> str:
        c = self.peek()
        if c == '"':
            return self.quoted()
        if c == "" or c == " " or c in SIGILS:
            self.error("expected a type name")
        if c == "-" or c == "%":
            self.error(f"a name starting with {c!r} must be quoted")
        words = [self.word()]
        while True:
            start = self.i
            self.skip_spaces()
            c = self.peek()
            if self.i == start or c in ("", " ") or c in SIGILS:
                self.i = start
                return " ".join(words)
            words.append(self.word())

    def type_ref(self) -> TypeRef:
        """A type name, and the type ID after it if there is one (§6.13)."""
        if self.peek() == '"':
            name = self.quoted()
            match = _TYPE_ID.match(self.s, self.i)
            if not match:
                return TypeRef(name)
            self.i = match.end()
            return TypeRef(name, self._type_id(match.group(1)))
        name = self.type_name()
        match = _NAME_WITH_ID.fullmatch(name)
        if not match:
            return TypeRef(name)
        return TypeRef(match.group(1), self._type_id(match.group(2)))

    def _type_id(self, digits: str) -> int:
        digits = digits.lstrip("0") or "0"
        if len(digits) > 10 or int(digits) > UINT32_MAX:
            self.error("a type ID is too large")
        return int(digits)

    def location(self) -> tuple[str, int | None]:
        match = _LOCATION.match(self.s, self.i)
        if not match:
            self.error(f"unknown location {self.token()!r}")
        self.i = match.end()
        name, index = match.group(1), match.group(2)
        if index:
            if name not in PINNABLE:
                self.error(f"unknown rack {name!r}")
            return name, self.positive(index, "a slot number")
        if name not in STORED and name not in PINNABLE:
            self.error(f"unknown location {name!r}")
        return name, None

    def overrides(self) -> list[tuple[str, str]]:
        self.i += 1
        self.skip_spaces()
        pairs = []
        while True:
            match = _OVERRIDE.match(self.s, self.i)
            if not match:
                self.error("malformed override; expected 'attribute value'")
            pairs.append((match.group(1), match.group(2)))
            self.i = match.end()
            self.skip_spaces()
            if self.peek() == ",":
                self.i += 1
                self.skip_spaces()
                continue
            if self.peek() == "}":
                self.i += 1
                return pairs
            self.error("malformed overrides; expected ',' or '}'")


def _hull(header: int, cur: _Cursor) -> FitBlock:
    block = FitBlock(header, cur.number)
    cur.skip_spaces()
    if cur.token() == "-":
        cur.i += 1
        if cur.next_element():
            if cur.peek() != '"':
                cur.error("a hull line of '-' takes only a fit name")
            block.fit_name = cur.quoted()
        cur.finish()
        return block

    if is_count(cur.token()):
        cur.error("the hull line cannot have a count")
    block.hull = cur.type_ref()
    more = cur.next_element()
    if more and cur.peek() == '"':
        block.fit_name = cur.quoted()
        more = cur.next_element()
    if more:
        if cur.peek() != "/":
            cur.error(f"unexpected {cur.token()!r} on the hull line")
        cur.i += 1
        block.mode = cur.type_name()
    cur.finish()
    return block


def _entry(cur: _Cursor) -> EmptyLine | ItemLine:
    cur.skip_spaces()
    count = cur.count()

    if cur.token() == "-":
        cur.i += 1
        if not cur.next_element() or cur.peek() != "@":
            cur.error("an empty slot must name its rack")
        rack, index = cur.location()
        if rack not in PINNABLE:
            cur.error("an empty slot must name a rack")
        if index is not None and count is not None:
            cur.error("a count and a pinned slot are mutually exclusive")
        cur.finish()
        return EmptyLine(cur.number, rack, count, index)

    line = ItemLine(cur.number, cur.type_ref(), count)
    more = cur.next_element()

    if more and cur.peek() == '"':
        line.fit_name = cur.quoted()
        if cur.next_element():
            if cur.peek() != "@":
                cur.error("a reference takes only a count and a location")
            line.location, index = cur.location()
            if index is not None or line.location not in STORED:
                cur.error("a reference can only be stored")
            cur.finish()
        return line

    stage = 0
    while more:
        c = cur.peek()
        if c == ":" and stage < 1:
            cur.i += 1
            line.charge_count = cur.count()
            line.charge = cur.type_ref()
            stage = 1
        elif c == "+" and stage < 2:
            cur.i += 1
            line.mutaplasmid = cur.type_name()
            stage = 2
        elif c == "{" and stage < 3:
            line.overrides = cur.overrides()
            stage = 3
        elif c == "!" and stage < 4:
            match = _STATE.match(cur.s, cur.i)
            if not match:
                cur.error(f"unknown state {cur.token()!r}")
            line.state = match.group(1)
            cur.i = match.end()
            stage = 4
        elif c == "@" and stage < 5:
            line.location, line.index = cur.location()
            if line.index is None and line.location not in STORED:
                cur.error("an item names a rack only to pin a slot, which needs an index")
            if line.index is not None and count is not None and line.location != TUBE:
                cur.error("a count and a pinned slot are mutually exclusive")
            stage = 5
        else:
            cur.error(f"unexpected {cur.token()!r}")
        more = cur.next_element()
    return line


def _is_blank(text: str) -> bool:
    stripped = text.lstrip(" ")
    return stripped == "" or stripped.startswith("//")


def parse(data: bytes) -> tuple[list[FitBlock], list[TextExtra]]:
    """Split a text document into fits and the other blocks."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as e:
        raise EsfFormatError(f"not valid UTF-8 at byte {e.start}") from None

    lines = text.split("\n")
    if lines[-1] == "":
        lines.pop()

    fits: list[FitBlock] = []
    extras: list[TextExtra] = []
    extra_start: int | None = None
    start = 0
    current: FitBlock | None = None
    header: int | None = None  # an esf header still waiting for its hull line
    in_block = False
    for number, raw in enumerate(lines, 1):
        line_start, start = start, start + len(raw) + 1
        raw = raw.removesuffix("\r")
        if "\r" in raw:
            raise EsfFormatError("a CR must be followed by an LF", number)

        if raw.lstrip(" ").startswith("%"):
            match = _HEADER.fullmatch(raw)
            if not match:
                raise EsfFormatError("malformed header", number)
            if header is not None:
                raise EsfFormatError("a fit needs a hull line", header)
            if extra_start is not None:
                extras[-1].text = text[extra_start:line_start]
            in_block = True
            current = None
            extra_start = None
            if match.group(1) == "esf":
                if match.group(2) != "1":
                    raise EsfFormatError(f"unsupported version esf/{match.group(2)}", number)
                header = number
            else:
                version = match.group(2).lstrip("0") or "0"
                if len(version) > 10 or int(version) > UINT32_MAX:
                    raise EsfFormatError("a block version is too large", number)
                extras.append(TextExtra(match.group(1), int(version), ""))
                extra_start = min(start, len(text))
            continue

        if not in_block:
            raise EsfFormatError("a document starts with a header", number)
        if _is_blank(raw):
            continue

        cur = _Cursor(number, raw)
        if header is not None:
            current = _hull(header, cur)
            fits.append(current)
            header = None
        elif current is not None:
            current.lines.append(_entry(cur))

    if header is not None:
        raise EsfFormatError("a fit needs a hull line", header)
    if not fits:
        raise EsfFormatError("a document holds at least one fit")
    if extra_start is not None:
        extras[-1].text = text[extra_start:]
    return fits, extras
