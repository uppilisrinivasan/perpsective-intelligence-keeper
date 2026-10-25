"""`python -m lamina.cli get FILE section.key` and `check FILE`."""

from __future__ import annotations

import sys

from lamina.errors import LaminaError
from lamina.loader import load


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args or args[0] not in ("get", "check"):
        print("usage: lamina (get FILE KEY | check FILE)", file=sys.stderr)
        return 2
    try:
        if args[0] == "check" and len(args) == 2:
            load(args[1], strict=False)
            print("ok")
            return 0
        if args[0] == "get" and len(args) == 3:
            value = load(args[1], strict=False).get(args[2])
            if value is None:
                print(f"not found: {args[2]}", file=sys.stderr)
                return 1
            print(value)
            return 0
    except LaminaError as e:
        print(f"error: {e}", file=sys.stderr)
        return 1
    print("usage: lamina (get FILE KEY | check FILE)", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(main())
