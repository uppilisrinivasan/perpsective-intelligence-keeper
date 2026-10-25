"""Build the sdist and wheel from the checked-out tree. Reproducible: nothing is fetched at build time."""

import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]


def main() -> int:
    version = (ROOT / "lamina" / "__init__.py").read_text(encoding="utf-8").split('__version__ = "')[1].split('"')[0]
    print(f"building lamina {version}")
    return subprocess.call([sys.executable, "-m", "build", str(ROOT)])


if __name__ == "__main__":
    sys.exit(main())
