"""Reading the text form into lines, without a Catalog (SPEC §4.1, grammar.ebnf)."""

import re
from dataclasses import dataclass, field

SIGILS = frozenset(':+{!@/"')
RACKS = ("sub", "high", "mid", "low", "rig", "svc")
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

_COUNT = re.compile(r"[0-9]+x")
_HEADER = re.compile(r" *%([a-z][a-z0-9-]*)/([0-9]+) *")
_STATE = re.compile(r"!(off|on|heat)")
_LOCATION = re.compile(r"@([a-z]+)([0-9]*)")
_OVERRIDE = re.compile(r"([A-Za-z][A-Za-z0-9]*) +(-?[0-9]+(?:\.[0-9]+)?)")


class EsfError(Exception):
    def __init__(self, message: str, line: int | None = None):
        super().__init__(message)
        self.message = message
        self.line = line

    def __str__(self) -> str:
        if self.line is None:
            return self.message
        return f"line {self.line}: {self.message}"


@dataclass
class Line:
    number: int
    kind: str  # "item", "empty" or "reference"
    count: int | None = None
    name: str | None = None
    fit_name: str | None = None
    charge: str | None = None
    charge_count: int | None = None
    mutaplasmid: str | None = None
    overrides: list[tuple[str, str]] = field(default_factory=list)
    state: str | None = None
    location: str | None = None
    index: int | None = None


@dataclass
class FitBlock:
    number: int
    hull: str | None = None
    hull_line: int | None = None
    fit_name: str | None = None
    mode: str | None = None
    lines: list[Line] = field(default_factory=list)


def is_count(token: str) -> bool:
    return _COUNT.fullmatch(token) is not None


class _Cursor:
    def __init__(self, number: int, text: str):
        self.number = number
        self.s = text
        self.i = 0

    def error(self, message: str):
        raise EsfError(message, self.number)

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

    def finish(self):
        if self.next_element():
            self.error(f"unexpected {self.token()!r}")

    def count(self) -> int | None:
        token = self.token()
        if not is_count(token):
            return None
        self.i += len(token)
        if not self.next_element():
            self.error("a count must be followed by a type name")
        if int(token[:-1]) == 0:
            self.error("a count must be at least 1")
        return int(token[:-1])

    def quoted(self) -> str:
        self.i += 1
        out = []
        while True:
            if self.i >= len(self.s):
                self.error("unterminated quoted string")
            c = self.s[self.i]
            if c == '"':
                if self.s.startswith('""', self.i):
                    out.append('"')
                    self.i += 2
                    continue
                self.i += 1
                break
            out.append(c)
            self.i += 1
        if not out:
            self.error("a quoted string cannot be empty")
        return "".join(out)

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

    def location(self) -> tuple[str, int | None]:
        match = _LOCATION.match(self.s, self.i)
        if not match:
            self.error(f"unknown location {self.token()!r}")
        self.i = match.end()
        name, index = match.group(1), match.group(2)
        if index:
            if name not in RACKS:
                self.error(f"unknown rack {name!r}")
            if int(index) == 0:
                self.error("slots are numbered from 1")
            return name, int(index)
        if name not in STORED and name not in RACKS:
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


def _hull(block: FitBlock, cur: _Cursor):
    block.hull_line = cur.number
    cur.skip_spaces()
    if cur.token() == "-":
        cur.i += 1
        if cur.next_element():
            if cur.peek() != '"':
                cur.error("a hull line of '-' takes only a fit name")
            block.fit_name = cur.quoted()
        cur.finish()
        return

    if is_count(cur.token()):
        cur.error("the hull line cannot have a count")
    block.hull = cur.type_name()
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


def _entry(cur: _Cursor) -> Line:
    cur.skip_spaces()
    count = cur.count()

    if cur.token() == "-":
        cur.i += 1
        if not cur.next_element() or cur.peek() != "@":
            cur.error("an empty slot must name its rack")
        rack, index = cur.location()
        if rack not in RACKS:
            cur.error("an empty slot must name a rack")
        if index is not None and count is not None:
            cur.error("a count and a pinned slot are mutually exclusive")
        cur.finish()
        return Line(cur.number, "empty", count=count, location=rack, index=index)

    line = Line(cur.number, "item", count=count, name=cur.type_name())
    more = cur.next_element()

    if more and cur.peek() == '"':
        line.kind = "reference"
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
            line.charge = cur.type_name()
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
            if line.index is not None and count is not None:
                cur.error("a count and a pinned slot are mutually exclusive")
            stage = 5
        else:
            cur.error(f"unexpected {cur.token()!r}")
        more = cur.next_element()
    return line


def _is_blank(text: str) -> bool:
    stripped = text.lstrip(" ")
    return stripped == "" or stripped.startswith("//")


def parse(data: bytes) -> list[FitBlock]:
    """Split a text document into fits; other blocks are skipped."""
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as e:
        raise EsfError(f"not valid UTF-8 at byte {e.start}") from None

    lines = text.split("\n")
    if lines[-1] == "":
        lines.pop()
    if not lines:
        raise EsfError("the document is empty")

    fits: list[FitBlock] = []
    current: FitBlock | None = None
    in_block = False
    for number, raw in enumerate(lines, 1):
        raw = raw.removesuffix("\r")
        if "\r" in raw:
            raise EsfError("a CR must be followed by an LF", number)

        if raw.lstrip(" ").startswith("%"):
            match = _HEADER.fullmatch(raw)
            if not match:
                raise EsfError("malformed header", number)
            if current is not None and current.hull_line is None:
                raise EsfError("a fit needs a hull line", current.number)
            in_block = True
            current = None
            if match.group(1) == "esf":
                if match.group(2) != "1":
                    raise EsfError(f"unsupported version esf/{match.group(2)}", number)
                current = FitBlock(number)
                fits.append(current)
            continue

        if not in_block:
            raise EsfError("a document starts with a header", number)
        if current is None or _is_blank(raw):
            continue

        cur = _Cursor(number, raw)
        if current.hull_line is None:
            _hull(current, cur)
        else:
            current.lines.append(_entry(cur))

    if current is not None and current.hull_line is None:
        raise EsfError("a fit needs a hull line", current.number)
    if not fits:
        raise EsfError("a document holds at least one fit")
    return fits
