"""Write a Document back to text. dumps(loads(text)) == text for any text loads accepts."""

from typing import TextIO

from lamina.model import Blank, Comment, Document, Entry, Section


def _item(item: object) -> str:
    if isinstance(item, Entry):
        if item.raw is not None:
            return item.raw
        line = f"{item.key} = {item.value}"
        return f"{line}  {item.note}" if item.note else line
    if isinstance(item, Comment):
        return item.text
    if isinstance(item, Blank):
        return ""
    raise TypeError(f"cannot write {type(item).__name__}")


def _section(section: Section) -> list[str]:
    head = section.raw if section.raw is not None else f"[{section.name}]"
    return [head] + [_item(i) for i in section.items]


def dumps(doc: Document) -> str:
    """Serialise doc, preserving order, comments and blank lines."""
    lines = [_item(i) for i in doc.preamble]
    for section in doc.sections():
        lines.extend(_section(section))
    return "\n".join(lines) + ("\n" if lines else "")


def dump(doc: Document, fp: TextIO) -> None:
    fp.write(dumps(doc))
