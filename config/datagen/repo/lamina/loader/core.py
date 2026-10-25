"""The public load API. There is deliberately no cache here: see the loader notes in CONTRIBUTING.md."""

from __future__ import annotations

import os
from collections.abc import Mapping

from lamina.include import expand_includes
from lamina.interpolate import interpolate_document
from lamina.model import Document
from lamina.parser import parse


def _read(path: str) -> Document:
    with open(path, encoding="utf-8") as fh:
        return parse(fh.read(), source=path)


def loads(text: str, *, env: Mapping[str, str] | None = None, root: str | None = None,
          base_dir: str = ".", strict: bool = True) -> Document:
    """Parse text. Includes are resolved under root (default: base_dir); env enables interpolation."""
    doc = parse(text)
    if doc.includes:
        doc = expand_includes(doc, base_dir, root or base_dir, _read)
    if env is not None:
        doc = interpolate_document(doc, env)
    elif strict:
        for section in doc.sections():
            for entry in section.entries():
                if "${" in entry.value:
                    from lamina.errors import InterpolationError
                    raise InterpolationError(f"{entry.key} needs an environment (pass env=)", entry.line, 1)
    return doc


def load(path: str, *, env: Mapping[str, str] | None = None, root: str | None = None,
         strict: bool = True) -> Document:
    """Read and parse a file."""
    with open(path, encoding="utf-8") as fh:
        text = fh.read()
    base = os.path.dirname(os.path.abspath(path))
    doc = loads(text, env=env, root=root or base, base_dir=base, strict=strict)
    doc.source = path
    return doc
