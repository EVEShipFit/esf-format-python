"""Name matching rules (SPEC §6.10, §6.1, §6.6)."""


def _fold_char(c: str) -> str:
    folded = c.casefold()
    if len(folded) == 1:
        return folded
    lowered = c.lower()
    return lowered if len(lowered) == 1 else c


def fold(s: str) -> str:
    """Unicode simple case folding."""
    return "".join(_fold_char(c) for c in s)


def is_word_prefix(prefix: str, name: str) -> bool:
    """Whether `prefix` is `name` with zero or more whole words dropped from the end."""
    words = fold(prefix).split(" ")
    full = fold(name).split(" ")
    return words == full[: len(words)]


def shortest_unique(name: str, others: list[str]) -> str:
    """The fewest leading words of `name` that are a word prefix of no name in `others`."""
    words = name.split(" ")
    for n in range(1, len(words) + 1):
        candidate = " ".join(words[:n])
        if not any(is_word_prefix(candidate, other) for other in others):
            return candidate
    return name
