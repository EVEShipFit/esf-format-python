"""The program the esf-format test runner calls: program.py check|canonical|binary."""

import os
import sys

from catalog import JsonCatalog

import esf_format


def main() -> int:
    command = sys.argv[1]
    catalog = JsonCatalog(os.environ["ESF_CATALOG"])
    try:
        fits = esf_format.load(sys.stdin.buffer.read(), catalog)
        if command == "canonical":
            sys.stdout.buffer.write(esf_format.save(fits, catalog).encode())
        elif command == "binary":
            sys.stdout.buffer.write(esf_format.save_binary(fits, catalog))
    except esf_format.EsfError as e:
        print(f"invalid: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
