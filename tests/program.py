"""The program the esf-format test runner calls: program.py check|canonical|binary|extra."""

import json
import os
import sys

from catalog import JsonCatalog

import esf_format


def main() -> int:
    command = sys.argv[1]
    catalog = JsonCatalog(os.environ["ESF_CATALOG"])
    try:
        document = esf_format.load_document(sys.stdin.buffer.read(), catalog)
        fits = document.fits
        if command == "extra":
            for e in document.extra:
                if isinstance(e, esf_format.TextExtra):
                    line = {"name": e.name, "version": e.version, "text": e.text}
                else:
                    line = {"field": e.field, "bytes": esf_format.to_base64url(e.bytes)}
                print(json.dumps(line))
        elif command == "canonical":
            sys.stdout.buffer.write(esf_format.save(fits, catalog).encode())
        elif command == "binary":
            sys.stdout.buffer.write(esf_format.save_binary(fits, catalog))
    except esf_format.EsfError as e:
        print(f"invalid: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
