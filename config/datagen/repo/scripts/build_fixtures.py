"""Regenerate the binary test fixtures in tests/data from their text sources, and print their checksums."""

import gzip
import hashlib
import pathlib

DATA = pathlib.Path(__file__).resolve().parents[1] / "tests" / "data"


def main() -> None:
    for src in sorted(DATA.glob("*.conf")):
        out = src.with_suffix(".conf.gz")
        out.write_bytes(gzip.compress(src.read_bytes(), mtime=0))
        print(out.name, hashlib.sha256(out.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
