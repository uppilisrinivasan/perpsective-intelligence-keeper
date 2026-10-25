"""${NAME} and ${NAME:-default} expansion. Environment values are secrets in practice: they never appear in
error messages or logs, only the variable names do."""

from collections.abc import Mapping

from lamina.errors import InterpolationError
from lamina.model import Document


def interpolate(value: str, env: Mapping[str, str], line: int = 0) -> str:
    """Expand references in one value."""
    out: list[str] = []
    i = 0
    while True:
        start = value.find("${", i)
        if start < 0:
            out.append(value[i:])
            return "".join(out)
        end = value.find("}", start + 2)
        if end < 0:
            raise InterpolationError("unterminated ${ reference", line, start + 1)
        out.append(value[i:start])
        name, sep, default = value[start + 2:end].partition(":-")
        if not name or not name.replace("_", "").isalnum():
            raise InterpolationError(f"invalid variable name {name!r}", line, start + 1)
        if name in env and env[name] != "":
            out.append(env[name])
        elif sep:
            out.append(default)
        else:
            raise InterpolationError(f"undefined variable {name}", line, start + 1)
        i = end + 1


def interpolate_document(doc: Document, env: Mapping[str, str]) -> Document:
    """Return a copy of doc with every value expanded."""
    result = doc.copy()
    for section in result.sections():
        for entry in section.entries():
            expanded = interpolate(entry.value, env, entry.line)
            if expanded != entry.value:
                entry.value = expanded
                entry.raw = None
    return result
