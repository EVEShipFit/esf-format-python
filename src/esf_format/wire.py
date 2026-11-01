"""The Protocol Buffers wire format."""

import struct

from .text import EsfError

VARINT, I64, LEN, SGROUP, EGROUP, I32 = range(6)
U64 = (1 << 64) - 1


def varint(value: int) -> bytes:
    out = bytearray()
    while value > 0x7F:
        out.append(value & 0x7F | 0x80)
        value >>= 7
    out.append(value)
    return bytes(out)


def key(field: int, wire: int) -> bytes:
    return varint(field << 3 | wire)


def uint(field: int, value: int) -> bytes:
    return key(field, VARINT) + varint(value)


def record(field: int, payload: bytes) -> bytes:
    return key(field, LEN) + varint(len(payload)) + payload


def packed_uints(field: int, values: list[int]) -> bytes:
    return record(field, b"".join(varint(v) for v in values))


def packed_doubles(field: int, values: list[float]) -> bytes:
    return record(field, struct.pack(f"<{len(values)}d", *values))


class Reader:
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def done(self) -> bool:
        return self.pos >= len(self.data)

    def take(self, n: int) -> bytes:
        if self.pos + n > len(self.data):
            raise EsfError("binary: not valid Protocol Buffers (cut short)")
        out = self.data[self.pos : self.pos + n]
        self.pos += n
        return out

    def varint(self) -> int:
        value = 0
        for shift in range(0, 70, 7):
            byte = self.take(1)[0]
            value |= (byte & 0x7F) << shift
            if not byte & 0x80:
                return value & U64
        raise EsfError("binary: not valid Protocol Buffers (varint is too long)")

    def key(self) -> tuple[int, int]:
        k = self.varint()
        field, wire = k >> 3, k & 7
        if field == 0 or k > 0xFFFFFFFF or wire > I32:
            raise EsfError(f"binary: not valid Protocol Buffers (bad key {k})")
        return field, wire

    def value(self, field: int, wire: int):
        """Read one value: an int for VARINT, bytes otherwise, None for a group."""
        if wire == VARINT:
            return self.varint()
        if wire == I64:
            return self.take(8)
        if wire == I32:
            return self.take(4)
        if wire == LEN:
            return self.take(self.varint())
        if wire == SGROUP:
            self.skip_group(field)
            return None
        raise EsfError("binary: not valid Protocol Buffers (unmatched end group)")

    def skip_group(self, field: int):
        open_groups = [field]
        while open_groups:
            inner, inner_wire = self.key()
            if inner_wire == SGROUP:
                open_groups.append(inner)
            elif inner_wire == EGROUP:
                if open_groups.pop() != inner:
                    raise EsfError("binary: not valid Protocol Buffers (unmatched end group)")
            else:
                self.value(inner, inner_wire)


def fields(data: bytes):
    """The (field, wire type, value) records of one message."""
    reader = Reader(data)
    while not reader.done():
        field, wire = reader.key()
        yield field, wire, reader.value(field, wire)


def unpack_uints(payload: bytes) -> list[int]:
    reader = Reader(payload)
    out = []
    while not reader.done():
        out.append(reader.varint())
    return out


def unpack_doubles(payload: bytes) -> list[float]:
    if len(payload) % 8:
        raise EsfError("binary: not valid Protocol Buffers (packed doubles cut short)")
    return list(struct.unpack(f"<{len(payload) // 8}d", payload))
