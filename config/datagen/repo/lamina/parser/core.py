"""Tokens to a Document. Keeps the raw lines so unchanged entries are written back byte for byte."""

from lamina.errors import ParseError
from lamina.lexer import Token, tokenize
from lamina.model import Blank, Comment, Document, Entry, Section


def parse(text: str, source: str = "<string>") -> Document:
    """Parse lamina text into a Document."""
    return parse_tokens(tokenize(text), text.splitlines(), source)


def parse_tokens(tokens: list[Token], lines: list[str], source: str = "<string>") -> Document:
    doc = Document(source=source)
    current: Section | None = None
    seen: set[str] = set()
    for tok in tokens:
        raw = lines[tok.line - 1] if 0 < tok.line <= len(lines) else None
        if tok.kind == "SECTION":
            if tok.value in seen:
                raise ParseError(f"duplicate section [{tok.value}]", tok.line, tok.column)
            seen.add(tok.value)
            current = Section(tok.value, line=tok.line, raw=raw)
            doc.sections_.append(current)
            continue
        if tok.kind == "ENTRY":
            value, _, note = tok.extra.partition("\x00")
            item = Entry(tok.value, value, note=note, line=tok.line, raw=raw)
            if current is None:
                raise ParseError(f"entry {tok.value!r} is outside any section", tok.line, tok.column)
            if tok.value in current.keys():
                raise ParseError(f"duplicate key {tok.value!r} in [{current.name}]", tok.line, tok.column)
            current.items.append(item)
            continue
        if tok.kind == "INCLUDE":
            doc.includes.append(tok.value)
            node: Comment | Blank = Comment(raw if raw is not None else f'@include "{tok.value}"', tok.line)
        elif tok.kind == "COMMENT":
            node = Comment(tok.value, tok.line)
        else:
            node = Blank(tok.line)
        (current.items if current is not None else doc.preamble).append(node)
    return doc
