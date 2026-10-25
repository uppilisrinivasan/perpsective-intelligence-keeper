"""Line-based tokenizer. This is the hot path: no regular expressions or per-character allocation here."""

from typing import NamedTuple

from lamina.errors import ParseError


class Token(NamedTuple):
    kind: str  # SECTION | ENTRY | COMMENT | BLANK | INCLUDE
    value: str
    line: int
    column: int
    extra: str = ""


def _strip_inline_comment(value: str) -> tuple[str, str]:
    """Split ``value  # note`` into (value, '# note'), respecting double quotes."""
    in_quotes = False
    for i, ch in enumerate(value):
        if ch == '"':
            in_quotes = not in_quotes
        elif ch == "#" and not in_quotes and (i == 0 or value[i - 1] in " \t"):
            return value[:i].rstrip(), value[i:]
    return value, ""


def tokenize(text: str) -> list[Token]:
    """Turn text into one token per line."""
    tokens: list[Token] = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        stripped = raw.strip()
        indent = len(raw) - len(raw.lstrip())
        column = indent + 1
        if not stripped:
            tokens.append(Token("BLANK", "", lineno, 1))
        elif stripped[0] in "#;":
            tokens.append(Token("COMMENT", raw, lineno, column))
        elif stripped.startswith("["):
            if not stripped.endswith("]") or len(stripped) < 3:
                raise ParseError("section header must look like [name]", lineno, column)
            tokens.append(Token("SECTION", stripped[1:-1].strip(), lineno, column))
        elif stripped.startswith("@include"):
            target = stripped[len("@include"):].strip()
            if len(target) < 2 or target[0] != '"' or target[-1] != '"':
                raise ParseError('include must look like @include "path"', lineno, column)
            tokens.append(Token("INCLUDE", target[1:-1], lineno, column))
        elif "=" in stripped:
            key, _, value = stripped.partition("=")
            key = key.strip()
            if not key:
                raise ParseError("missing key before '='", lineno, column)
            value, note = _strip_inline_comment(value.strip())
            tokens.append(Token("ENTRY", key, lineno, column, extra=value + ("\x00" + note if note else "")))
        else:
            raise ParseError(f"cannot parse line: {stripped[:40]}", lineno, column)
    return tokens
