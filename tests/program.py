"""The program the esf-format test runner calls: program.py check|canonical|binary."""

import os
import sys

from catalog import JsonCatalog

import esf_format


def main() -> int:
    command = sys.argv[1]
    catalog = JsonCatalog(os.environ["ESF_CATALOG"])
    try:
        fits = esf_format.read(sys.stdin.buffer.read(), catalog)
    except esf_format.EsfError as e:
        print(f"invalid: {e}", file=sys.stderr)
        return 1
    if command == "canonical":
        sys.stdout.buffer.write(esf_format.to_text(fits).encode())
    elif command == "binary":
        sys.stdout.buffer.write(esf_format.to_binary(fits))
    return 0


if __name__ == "__main__":
    sys.exit(main())
