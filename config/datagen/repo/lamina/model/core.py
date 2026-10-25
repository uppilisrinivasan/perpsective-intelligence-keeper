"""The document model keeps everything needed to write the text back unchanged: order, comments, blank lines."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Union


@dataclass
class Entry:
    key: str
    value: str
    note: str = ""
    line: int = 0
    raw: str | None = None  # the original line, reused when the entry is unchanged


@dataclass
class Comment:
    text: str
    line: int = 0


@dataclass
class Blank:
    line: int = 0


Item = Union[Entry, Comment, Blank]


@dataclass
class Section:
    name: str
    items: list[Item] = field(default_factory=list)
    line: int = 0
    raw: str | None = None

    def entries(self) -> list[Entry]:
        return [i for i in self.items if isinstance(i, Entry)]

    def keys(self) -> list[str]:
        return [e.key for e in self.entries()]

    def get(self, key: str, default: str | None = None) -> str | None:
        for e in self.entries():
            if e.key == key:
                return e.value
        return default

    def set(self, key: str, value: str) -> None:
        for e in self.entries():
            if e.key == key:
                if e.value != value:
                    e.value = value
                    e.raw = None
                return
        self.items.append(Entry(key, value))

    def remove(self, key: str) -> bool:
        for i, item in enumerate(self.items):
            if isinstance(item, Entry) and item.key == key:
                del self.items[i]
                return True
        return False


@dataclass
class Document:
    preamble: list[Item] = field(default_factory=list)
    sections_: list[Section] = field(default_factory=list)
    source: str = "<string>"
    includes: list[str] = field(default_factory=list)

    def sections(self) -> list[Section]:
        return list(self.sections_)

    def section(self, name: str, create: bool = False) -> Section | None:
        for s in self.sections_:
            if s.name == name:
                return s
        if create:
            s = Section(name)
            self.sections_.append(s)
            return s
        return None

    def get(self, dotted: str, default: str | None = None) -> str | None:
        name, _, key = dotted.rpartition(".")
        sec = self.section(name)
        return sec.get(key, default) if sec else default

    def to_dict(self) -> dict[str, dict[str, str]]:
        return {s.name: {e.key: e.value for e in s.entries()} for s in self.sections_}

    def copy(self) -> Document:
        import copy

        return copy.deepcopy(self)
