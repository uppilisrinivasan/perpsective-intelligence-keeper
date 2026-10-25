"""Include resolution. Included files come from configuration that may be untrusted, so every resolved path
must stay inside the project root (symlinks included) and include chains have a depth limit."""

from __future__ import annotations

import os
from collections.abc import Callable

from lamina.errors import IncludeError
from lamina.model import Document

MAX_DEPTH = 8


def resolve_include(base_dir: str, name: str, root: str, line: int = 0) -> str:
    """Resolve an include name relative to base_dir; the result must stay inside root."""
    root_real = os.path.realpath(root)
    candidate = os.path.realpath(os.path.join(base_dir, name))
    if os.path.commonpath([candidate, root_real]) != root_real:
        raise IncludeError(f"include escapes the project root: {name}", line, 1)
    if not os.path.isfile(candidate):
        raise IncludeError(f"include not found: {name}", line, 1)
    return candidate


def expand_includes(doc: Document, base_dir: str, root: str, read: Callable[[str], Document],
                    depth: int = 0, seen: frozenset[str] = frozenset()) -> Document:
    """Merge included documents under doc (doc's own values win). Detects cycles and enforces MAX_DEPTH."""
    if depth > MAX_DEPTH:
        raise IncludeError(f"includes nested deeper than {MAX_DEPTH}", 0, 1)
    merged = Document(source=doc.source)
    for name in doc.includes:
        path = resolve_include(base_dir, name, root)
        if path in seen:
            raise IncludeError(f"include cycle through {name}", 0, 1)
        child = expand_includes(read(path), os.path.dirname(path), root, read, depth + 1, seen | {path})
        for section in child.sections():
            target = merged.section(section.name, create=True)
            for entry in section.entries():
                target.set(entry.key, entry.value)
    for section in doc.sections():
        target = merged.section(section.name, create=True)
        for entry in section.entries():
            target.set(entry.key, entry.value)
    return merged
