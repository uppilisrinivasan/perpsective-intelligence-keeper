"""Code for the demo repository's pull requests (the role of datagen_pr_change, authored as templates).

Every feature is a pure function of (area, noun, toggles): each planted concern slot is one toggle, so an author's
fix-up is the same render with that toggle switched off, and git computes the real diff. Slot lines are tagged
while rendering so code knows exactly where each planted issue sits (the `issue_locations` of the change).
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field


def _h(*parts: object) -> int:
    return int(hashlib.sha256("|".join(map(str, parts)).encode()).hexdigest()[:8], 16)


@dataclass
class Feature:
    area: str
    noun: str
    pkg: str
    toggles: frozenset[str] = frozenset()
    variant: str | None = None
    rev: int = 0
    renames: dict[str, str] = field(default_factory=dict)  # E7: old keyword → new keyword
    deprecated: bool = False                                # E7 addressed: old name kept with a warning
    with_tests: bool = True

    def on(self, slot: str) -> bool:
        return slot in self.toggles


@dataclass
class Rendered:
    files: dict[str, str]
    locations: dict[str, tuple[str, int]]
    fn: str
    module_path: str
    test_path: str | None
    public_params: list[str]
    err_class: str
    branches: int


class _Code:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.tags: dict[str, int] = {}

    def add(self, text: str = "", tag: str | None = None) -> None:
        for i, part in enumerate(text.split("\n")):
            self.lines.append(part)
            if tag and i == 0 and tag not in self.tags:
                self.tags[tag] = len(self.lines)

    def text(self) -> str:
        return "\n".join(self.lines).rstrip("\n") + "\n"


def _sig(f: Feature, fn: str, params: list[tuple[str, str, str | None]], ret: str) -> str:
    """params: (name, annotation, default). D1 drops the annotations of the public function."""
    parts, kw = [], False
    for name, ann, default in params:
        if name == "*":
            parts.append("*")
            kw = True
            continue
        name = f.renames.get(name, name)
        if f.on("D1"):
            p = name if default is None else f"{name}={default}"
        else:
            p = f"{name}: {ann}" if default is None else f"{name}: {ann} = {default}"
        parts.append(p)
    if f.deprecated and f.renames:
        for old in f.renames:
            parts.append(f"{old}=None" if f.on("D1") else f"{old}: object = None")
    _ = kw
    return f"def {fn}({', '.join(parts)})" + ("" if f.on("D1") else f" -> {ret}") + ":"


def _doc(f: Feature, c: _Code, text: str) -> None:
    if not f.on("S3"):
        c.add(f'    """{text}"""')


def _deprecation_shim(f: Feature, c: _Code) -> None:
    for old, new in f.renames.items():
        c.add(f"    if {old} is not None:")
        c.add(f'        warnings.warn("{old}= is deprecated; use {new}=", DeprecationWarning, stacklevel=2)')
        c.add(f"        {new} = {old}  # type: ignore[assignment]")


def _camel(snake: str) -> str:
    head, *rest = snake.split("_")
    return head + "".join(p.title() for p in rest)


_ALT = {"resolved_path": "candidate_path", "out_parts": "pieces", "current_word": "word_buffer",
        "stripped_text": "text_value", "merged_doc": "result_doc", "pad_text": "prefix_text", "file_text": "raw_text",
        "full_message": "message_text", "source_text": "file_content"}


def _var(f: Feature, snake: str) -> str:
    """Local variable names: camelCase when S2 (a naming nit) is planted; a rewrite (rev) renames them."""
    name = _ALT.get(snake, snake) if f.rev % 2 else snake
    return _camel(name) if f.on("S2") and "_" in name else name


def _skip_param(f: Feature) -> tuple[str, str, str]:
    return ("skip", "list[str] | None" if not f.on("S4") else "list[str]", "[]" if f.on("S4") else "None")


def _skip_body(f: Feature, c: _Code, item: str) -> None:
    if f.on("S4"):
        c.add(f"    skip.append({item})", tag="S4")
    else:
        c.add("    skip = list(skip or [])")
        c.add(f"    skip.append({item})")


# ---------------------------------------------------------------------------------------------------- include
def _include(f: Feature) -> Rendered:
    pkg, n = f.pkg, f.noun
    fn, read_fn, walk = f"resolve_{n}_include", f"read_{n}_include", f"_walk_{n}"
    mod = f"{pkg}/include/{n}.py"
    c = _Code()
    c.add(f'"""{n.replace("_", " ").capitalize()} includes."""')
    c.add("")
    if f.on("S2") and _h(n) % 2:
        c.add("import sys")
    c.add("import os")
    if f.deprecated:
        c.add("import warnings")
    c.add("")
    c.add(f"from {pkg}.errors import IncludeError")
    c.add("")
    c.add("")
    c.add(_sig(f, fn, [("base_dir", "str", None), ("name", "str", None), ("root", "str", None), ("*", "", None),
                      _skip_param(f)], "str"))
    _doc(f, c, f"Resolve a {n.replace('_', ' ')} include relative to base_dir, confined to root.")
    if f.deprecated:
        _deprecation_shim(f, c)
    cand = _var(f, "resolved_path")
    _skip_body(f, c, "name")
    if f.on("E1") and f.variant == "absolute":
        c.add("    if os.path.isabs(name):", tag="E1")
        c.add("        return name")
    if f.on("E1") and f.variant == "dotdot":
        c.add(f"    {cand} = os.path.join(base_dir, name)", tag="E1")
    elif f.on("E1") and f.variant == "symlink":
        c.add("    root_real = os.path.abspath(root)")
        c.add(f"    {cand} = os.path.abspath(os.path.join(base_dir, name))", tag="E1")
        c.add(f"    if os.path.commonpath([{cand}, root_real]) != root_real:")
        c.add('        raise IncludeError(f"include escapes the project root: {name}", 0, 1)')
    else:
        c.add("    root_real = os.path.realpath(root)")
        c.add(f"    {cand} = os.path.realpath(os.path.join(base_dir, name))", tag="E1fix")
        c.add(f"    if os.path.commonpath([{cand}, root_real]) != root_real:")
        c.add('        raise IncludeError(f"include escapes the project root: {name}", 0, 1)')
    c.add(f"    if not os.path.isfile({cand}):")
    if f.on("E6"):
        c.add('        raise ValueError(f"include not found: {name}")', tag="E6")
    else:
        c.add('        raise IncludeError(f"include not found: {name}", 0, 1)')
    c.add(f"    return {cand}")
    c.add("")
    c.add("")
    c.add(f"def {read_fn}(base_dir: str, name: str, root: str) -> str:")
    c.add(f'    """Return the text of a {n.replace("_", " ")} include."""')
    c.add(f"    path = {fn}(base_dir, name, root)")
    if f.on("B2"):
        c.add('    fh = open(path, encoding="utf-8")', tag="B2")
        c.add("    text = fh.read()")
        c.add("    if not text.strip():")
        c.add('        raise IncludeError(f"empty include: {name}", 0, 1)')
        c.add("    fh.close()")
        c.add("    return text")
    else:
        enc = "" if f.on("B1") else ', encoding="utf-8"'
        c.add(f"    with open(path{enc}) as fh:", tag="B1" if f.on("B1") else None)
        c.add("        return fh.read()")
    if f.on("T3") or _h(n, "walk") % 3 == 0:
        c.add("")
        c.add("")
        c.add(f"def {walk}(base_dir: str, names: list[str], root: str, depth: int = 0) -> list[str]:")
        c.add('    """Resolve a chain of includes, depth first."""')
        if not f.on("T3"):
            c.add("    if depth > 8:")
            c.add('        raise IncludeError("includes nested too deeply", 0, 1)')
        c.add("    out: list[str] = []", tag="T3" if f.on("T3") else None)
        c.add("    for name in names:")
        c.add(f"        out.append({fn}(base_dir, name, root))")
        c.add("    if len(names) > 1:")
        c.add(f"        out.extend({walk}(base_dir, names[1:], root, depth + 1))")
        c.add("    return out")
    tests = None
    tpath = f"tests/test_include_{n}.py"
    if f.with_tests and not f.on("S1"):
        tests = (f"import pytest\n\nfrom {pkg}.include.{n} import {fn}, {read_fn}\n\n\n"
                 f"def test_{n}_include_reads_file(tmp_path):\n"
                 f"    (tmp_path / \"base.conf\").write_text(\"[a]\\nx = 1\\n\", encoding=\"utf-8\")\n"
                 f"    assert \"x = 1\" in {read_fn}(str(tmp_path), \"base.conf\", str(tmp_path))\n\n\n"
                 f"def test_{n}_include_missing(tmp_path):\n"
                 f"    with pytest.raises(Exception):\n"
                 f"        {fn}(str(tmp_path), \"nope.conf\", str(tmp_path))\n")
    return Rendered({mod: c.text(), **({tpath: tests} if tests else {})},
                    {k: (mod, v) for k, v in c.tags.items()}, fn, mod, tpath if tests else None,
                    ["base_dir", "name", "root", "skip"], "IncludeError", 3)


# ------------------------------------------------------------------------------------------------ interpolate
def _interpolate(f: Feature) -> Rendered:
    pkg, n = f.pkg, f.noun
    fn = f"interpolate_{n}"
    mod = f"{pkg}/interpolate/{n}.py"
    rules = ["value.isprintable()", "\"\\n\" not in value", "len(value) < 4096", "value.strip() == value"]
    rule = rules[_h(n) % len(rules)]
    c = _Code()
    c.add(f'"""{n.replace("_", " ").capitalize()} interpolation: ${{NAME}} references with extra checks."""')
    c.add("")
    if f.on("S2") and _h(n) % 2:
        c.add("import sys")
    c.add("from collections.abc import Mapping")
    if f.deprecated:
        c.add("import warnings")
    c.add("")
    c.add(f"from {pkg}.errors import InterpolationError")
    c.add("")
    c.add("")
    c.add("def _valid(value: str) -> bool:")
    c.add(f"    return {rule}")
    c.add("")
    c.add("")
    c.add(_sig(f, fn, [("value", "str", None), ("env", "Mapping[str, str]", None), ("*", "", None),
                      ("line", "int", "0"), _skip_param(f)], "str"))
    _doc(f, c, f"Expand ${{NAME}} references in value using env ({n.replace('_', ' ')} rules).")
    if f.deprecated:
        _deprecation_shim(f, c)
    _skip_body(f, c, "value")
    parts = _var(f, "out_parts")
    c.add(f"    {parts}: list[str] = []")
    c.add("    i = 0")
    c.add("    while True:")
    c.add('        start = value.find("${", i)')
    c.add("        if start < 0:")
    c.add(f"            {parts}.append(value[i:])")
    c.add(f'            return "".join({parts})')
    c.add('        end = value.find("}", start)')
    c.add("        if end < 0:")
    if f.on("E6"):
        c.add('            raise ValueError("unterminated reference")', tag="E6")
    else:
        c.add('            raise InterpolationError("unterminated reference", line, start + 1)')
    c.add(f"        {parts}.append(value[i:start])")
    c.add("        name = value[start + 2:end]")
    c.add("        if name not in env:")
    c.add('            raise InterpolationError(f"undefined variable {name}", line, start + 1)')
    c.add("        resolved = env[name]")
    c.add("        if not _valid(resolved):")
    if f.on("E8"):
        c.add('            raise InterpolationError(f"invalid value {resolved!r} for {name}", line, start + 1)',
              tag="E8")
    else:
        c.add('            raise InterpolationError(f"invalid value for {name}", line, start + 1)')
    c.add(f"        {parts}.append(resolved)")
    c.add("        i = end + 1")
    tests = None
    tpath = f"tests/test_interpolate_{n}.py"
    if f.with_tests and not f.on("S1"):
        tests = (f"import pytest\n\nfrom {pkg}.errors import InterpolationError\nfrom {pkg}.interpolate.{n} import {fn}\n\n\n"
                 f"def test_{n}_expands():\n    assert {fn}(\"a-${{X}}\", {{\"X\": \"1\"}}) == \"a-1\"\n\n\n"
                 f"def test_{n}_undefined():\n    with pytest.raises(InterpolationError):\n        {fn}(\"${{NOPE}}\", {{}})\n\n\n"
                 f"def test_{n}_plain_text():\n    assert {fn}(\"plain\", {{}}) == \"plain\"\n")
    return Rendered({mod: c.text(), **({tpath: tests} if tests else {})}, {k: (mod, v) for k, v in c.tags.items()},
                    fn, mod, tpath if tests else None, ["value", "env", "line", "skip"], "InterpolationError", 4)


# ------------------------------------------------------------------------------------------------------ lexer
def _lexer(f: Feature) -> Rendered:
    pkg, n = f.pkg, f.noun
    fn = f"scan_{n}"
    mod = f"{pkg}/lexer/{n}.py"
    seps = [",", "|", ":", ";", "/", "+"]
    sep = seps[_h(n) % len(seps)]
    c = _Code()
    c.add(f'"""{n.replace("_", " ").capitalize()} tokens inside a value (the tokenizer is the hot path)."""')
    c.add("")
    if f.on("E4"):
        c.add("import re")
    if f.on("S2") and _h(n) % 2:
        c.add("import sys")
    if f.deprecated:
        c.add("import warnings")
    if f.on("E4") or (f.on("S2") and _h(n) % 2) or f.deprecated:
        c.add("")
    c.add(f"from {pkg}.lexer.core import Token")
    c.add("")
    c.add("")
    c.add(_sig(f, fn, [("value", "str", None), ("line", "int", None), ("*", "", None), _skip_param(f)],
               "list[Token]"))
    _doc(f, c, f"Split value into {n.replace('_', ' ')} words, separated by {sep!r} or whitespace.")
    if f.deprecated:
        _deprecation_shim(f, c)
    _skip_body(f, c, "value")
    word = _var(f, "current_word")
    c.add("    tokens: list[Token] = []")
    c.add(f"    {word}: list[str] = []")
    c.add("    start = 1")
    c.add("    for column, ch in enumerate(value, start=1):")
    if f.on("E4"):
        cls_ = "[\\s" + sep + "]"
        c.add(f'        if re.match(r"{cls_}", ch):', tag="E4")
    else:
        c.add(f"        if ch.isspace() or ch == {sep!r}:")
    c.add(f"            if {word}:")
    c.add(f'                tokens.append(Token("WORD", "".join({word}), line, start))')
    c.add(f"                {word} = []")
    c.add("            continue")
    c.add(f"        if not {word}:")
    c.add("            start = column")
    c.add(f"        {word}.append(ch)")
    c.add(f"    if {word}:")
    c.add(f'        tokens.append(Token("WORD", "".join({word}), line, start))')
    c.add("    return tokens")
    tests = None
    tpath = f"tests/test_lexer_{n}.py"
    if f.with_tests and not f.on("S1"):
        tests = (f"from {pkg}.lexer.{n} import {fn}\n\n\n"
                 f"def test_{n}_words():\n    assert [t.value for t in {fn}(\"a{sep}b c\", 1)] == [\"a\", \"b\", \"c\"]\n\n\n"
                 f"def test_{n}_columns():\n    assert [t.column for t in {fn}(\"ab{sep}cd\", 3)] == [1, 4]\n\n\n"
                 f"def test_{n}_empty():\n    assert {fn}(\"\", 1) == []\n")
    return Rendered({mod: c.text(), **({tpath: tests} if tests else {})}, {k: (mod, v) for k, v in c.tags.items()},
                    fn, mod, tpath if tests else None, ["value", "line", "skip"], "ParseError", 3)


# ----------------------------------------------------------------------------------------------------- parser
def _parser(f: Feature) -> Rendered:
    pkg, n = f.pkg, f.noun
    fn = f"parse_{n}_value"
    mod = f"{pkg}/parser/{n}.py"
    c = _Code()
    c.add(f'"""Parse {n.replace("_", " ")} values: comma-separated items in brackets."""')
    c.add("")
    if f.on("S2") and _h(n) % 2:
        c.add("import sys")
    if f.deprecated:
        c.add("import warnings")
    if (f.on("S2") and _h(n) % 2) or f.deprecated:
        c.add("")
    c.add(f"from {pkg}.errors import ParseError")
    c.add("")
    c.add("")
    c.add(_sig(f, fn, [("raw", "str", None), ("line", "int", None), ("column", "int", None), ("*", "", None),
                      _skip_param(f)], "list[str]"))
    _doc(f, c, f"Parse a [a, b, c] {n.replace('_', ' ')} value into its items.")
    if f.deprecated:
        _deprecation_shim(f, c)
    _skip_body(f, c, "raw")
    text = _var(f, "stripped_text")
    c.add(f"    {text} = raw.strip()")
    c.add(f'    if not ({text}.startswith("[") and {text}.endswith("]")):')
    if f.on("E6"):
        c.add('        raise ValueError(f"expected [items], got {raw!r}")', tag="E6")
    else:
        c.add('        raise ParseError(f"expected [items], got {raw!r}", line, column)')
    c.add(f"    inner = {text}[1:-1].strip()")
    c.add("    if not inner:")
    c.add("        return []")
    c.add('    items = [part.strip() for part in inner.split(",")]')
    c.add('    if any(item == "" for item in items):')
    c.add('        raise ParseError("empty item in list", line, column)')
    c.add("    return items")
    tests = None
    tpath = f"tests/test_parser_{n}.py"
    if f.with_tests and not f.on("S1"):
        tests = (f"import pytest\n\nfrom {pkg}.parser.{n} import {fn}\n\n\n"
                 f"def test_{n}_items():\n    assert {fn}(\"[a, b]\", 1, 1) == [\"a\", \"b\"]\n\n\n"
                 f"def test_{n}_empty_list():\n    assert {fn}(\"[]\", 1, 1) == []\n\n\n"
                 f"def test_{n}_rejects_bare_value():\n    with pytest.raises(Exception):\n        {fn}(\"a, b\", 2, 5)\n")
    return Rendered({mod: c.text(), **({tpath: tests} if tests else {})}, {k: (mod, v) for k, v in c.tags.items()},
                    fn, mod, tpath if tests else None, ["raw", "line", "column", "skip"], "ParseError", 3)


# ------------------------------------------------------------------------------------------------ model, dump
def _model(f: Feature) -> Rendered:
    pkg, n = f.pkg, f.noun
    fn = f"merge_{n}"
    mod = f"{pkg}/model/{n}.py"
    c = _Code()
    c.add(f'"""Merge {n.replace("_", " ")} layers into a base document."""')
    c.add("")
    if f.on("S2") and _h(n) % 2:
        c.add("import sys")
    if f.deprecated:
        c.add("import warnings")
    if (f.on("S2") and _h(n) % 2) or f.deprecated:
        c.add("")
    c.add(f"from {pkg}.model import Document")
    c.add("")
    c.add("")
    c.add(_sig(f, fn, [("base", "Document", None), ("overlay", "Document", None), ("*", "", None),
                      ("create", "bool", "True"), _skip_param(f)], "Document"))
    _doc(f, c, "Return base with overlay's values applied, keeping base's order, comments and blank lines.")
    if f.deprecated:
        _deprecation_shim(f, c)
    _skip_body(f, c, "overlay.source")
    res = _var(f, "merged_doc")
    c.add(f"    {res} = base.copy()")
    c.add("    for section in overlay.sections():")
    c.add(f"        target = {res}.section(section.name, create={f.renames.get('create', 'create')})")
    c.add("        if target is None:")
    c.add("            continue")
    c.add("        for entry in section.entries():")
    c.add("            target.set(entry.key, entry.value)")
    if f.on("E2"):
        c.add("        target.items.sort(key=lambda item: getattr(item, \"key\", \"\"))", tag="E2")
    c.add(f"    return {res}")
    tests = None
    tpath = f"tests/test_model_{n}.py"
    if f.with_tests and not f.on("S1"):
        kw = f.renames.get("create", "create")
        tests = (f"from {pkg}.loader import loads\nfrom {pkg}.model.{n} import {fn}\n\n\n"
                 f"def test_{n}_overrides():\n    doc = {fn}(loads(\"[a]\\nx = 1\\n\"), loads(\"[a]\\nx = 2\\n\"))\n"
                 f"    assert doc.get(\"a.x\") == \"2\"\n\n\n"
                 f"def test_{n}_no_create():\n    doc = {fn}(loads(\"[a]\\nx = 1\\n\"), loads(\"[b]\\ny = 2\\n\"), {kw}=False)\n"
                 f"    assert doc.section(\"b\") is None\n")
    return Rendered({mod: c.text(), **({tpath: tests} if tests else {})}, {k: (mod, v) for k, v in c.tags.items()},
                    fn, mod, tpath if tests else None, ["base", "overlay", "create", "skip"], "LaminaError", 3)


def _dump(f: Feature) -> Rendered:
    pkg, n = f.pkg, f.noun
    fn = f"dumps_{n}"
    mod = f"{pkg}/dump/{n}.py"
    c = _Code()
    c.add(f'"""Write documents in the {n.replace("_", " ")} layout."""')
    c.add("")
    if f.on("S2") and _h(n) % 2:
        c.add("import sys")
    if f.deprecated:
        c.add("import warnings")
    if (f.on("S2") and _h(n) % 2) or f.deprecated:
        c.add("")
    c.add(f"from {pkg}.model import Blank, Comment, Document, Entry")
    c.add("")
    c.add("")
    c.add(_sig(f, fn, [("doc", "Document", None), ("*", "", None), ("indent", "int", "0"), _skip_param(f)], "str"))
    _doc(f, c, "Serialise doc with entries indented, preserving order, comments and blank lines.")
    if f.deprecated:
        _deprecation_shim(f, c)
    _skip_body(f, c, "doc.source")
    pad = _var(f, "pad_text")
    c.add(f'    {pad} = " " * {f.renames.get("indent", "indent")}')
    c.add("    lines: list[str] = []")
    c.add("    for section in doc.sections():")
    c.add('        lines.append(f"[{section.name}]")')
    if f.on("E2"):
        c.add("        for item in sorted(section.items, key=lambda i: getattr(i, \"key\", \"\")):", tag="E2")
    else:
        c.add("        for item in section.items:")
    c.add("            if isinstance(item, Entry):")
    c.add(f'                lines.append(f"{{{pad}}}{{item.key}} = {{item.value}}")')
    c.add("            elif isinstance(item, Comment):")
    c.add("                lines.append(item.text)")
    c.add("            elif isinstance(item, Blank):")
    c.add('                lines.append("")')
    c.add('    return "\\n".join(lines) + ("\\n" if lines else "")')
    tests = None
    tpath = f"tests/test_dump_{n}.py"
    if f.with_tests and not f.on("S1"):
        kw = f.renames.get("indent", "indent")
        tests = (f"from {pkg}.loader import loads\nfrom {pkg}.dump.{n} import {fn}\n\n\n"
                 f"def test_{n}_indents():\n    assert {fn}(loads(\"[a]\\nx = 1\\n\"), {kw}=2) == \"[a]\\n  x = 1\\n\"\n\n\n"
                 f"def test_{n}_keeps_comments():\n    assert \"# c\" in {fn}(loads(\"[a]\\n# c\\nx = 1\\n\"))\n\n\n"
                 f"def test_{n}_empty():\n    assert {fn}(loads(\"\")) == \"\"\n")
    return Rendered({mod: c.text(), **({tpath: tests} if tests else {})}, {k: (mod, v) for k, v in c.tags.items()},
                    fn, mod, tpath if tests else None, ["doc", "indent", "skip"], "LaminaError", 4)


# ----------------------------------------------------------------------------------------------------- loader
def _loader(f: Feature) -> Rendered:
    pkg, n = f.pkg, f.noun
    fn = f"load_{n}"
    mod = f"{pkg}/loader/{n}.py"
    c = _Code()
    c.add(f'"""Load {n.replace("_", " ")} configuration files."""')
    c.add("")
    if f.on("S2") and _h(n) % 2:
        c.add("import sys")
    c.add("import os")
    if f.deprecated:
        c.add("import warnings")
    c.add("")
    c.add(f"from {pkg}.errors import LaminaError")
    c.add(f"from {pkg}.loader.core import loads")
    if f.on("E5") or not f.on("D1"):
        c.add(f"from {pkg}.model import Document")
    if f.on("E5"):
        c.add("")
        c.add("_CACHE: dict[str, Document] = {}", tag="E5")
    c.add("")
    c.add("")
    c.add(_sig(f, fn, [("path", "str", None), ("*", "", None), ("strict", "bool", "True"), _skip_param(f)],
               "Document"))
    _doc(f, c, f"Load a {n.replace('_', ' ')} configuration file.")
    if f.deprecated:
        _deprecation_shim(f, c)
    _skip_body(f, c, "path")
    if f.on("E5"):
        c.add("    if path in _CACHE:")
        c.add("        return _CACHE[path]")
    txt = _var(f, "file_text")
    if f.on("B2"):
        c.add('    fh = open(path, encoding="utf-8")', tag="B2")
        c.add(f"    {txt} = fh.read()")
        c.add(f"    if {f.renames.get('strict', 'strict')} and not {txt}.strip():")
        c.add('        raise LaminaError(f"empty configuration: {path}", 0, 1)')
        c.add("    fh.close()")
    else:
        enc = "" if f.on("B1") else ', encoding="utf-8"'
        c.add(f"    with open(path{enc}) as fh:", tag="B1" if f.on("B1") else None)
        c.add(f"        {txt} = fh.read()")
        c.add(f"    if {f.renames.get('strict', 'strict')} and not {txt}.strip():")
        c.add('        raise LaminaError(f"empty configuration: {path}", 0, 1)')
    c.add(f'    doc = loads({txt}, base_dir=os.path.dirname(os.path.abspath(path)), strict=False)')
    c.add("    doc.source = path")
    if f.on("E5"):
        c.add("    _CACHE[path] = doc")
    c.add("    return doc")
    tests = None
    tpath = f"tests/test_loader_{n}.py"
    if f.with_tests and not f.on("S1"):
        kw = f.renames.get("strict", "strict")
        tests = (f"import pytest\n\nfrom {pkg}.loader.{n} import {fn}\n\n\n"
                 f"def test_{n}_loads(write):\n    path = write(\"a_{n}.conf\", \"[a]\\nx = 1\\n\")\n"
                 f"    assert {fn}(path).get(\"a.x\") == \"1\"\n\n\n"
                 f"def test_{n}_empty_strict(write):\n    path = write(\"e_{n}.conf\", \"\")\n"
                 f"    with pytest.raises(Exception):\n        {fn}(path, {kw}=True)\n\n\n"
                 f"def test_{n}_empty_lenient(write):\n    path = write(\"l_{n}.conf\", \"\")\n"
                 f"    assert {fn}(path, {kw}=False).sections() == []\n")
    return Rendered({mod: c.text(), **({tpath: tests} if tests else {})}, {k: (mod, v) for k, v in c.tags.items()},
                    fn, mod, tpath if tests else None, ["path", "strict", "skip"], "LaminaError", 3)


# ----------------------------------------------------------------------------------------------- errors, cli
def _errors(f: Feature) -> Rendered:
    pkg, n = f.pkg, f.noun
    cls = "".join(p.title() for p in n.split("_")) + "Error"
    fn = f"raise_{n}"
    mod = f"{pkg}/diagnostics/{n}.py"
    c = _Code()
    c.add(f'"""The {cls} error and its helper."""')
    c.add("")
    if f.on("S2") and _h(n) % 2:
        c.add("import sys")
        c.add("")
    if not f.on("E6"):
        c.add(f"from {pkg}.errors import LaminaError")
        c.add("")
        c.add("")
    if f.on("E6"):
        c.add(f"class {cls}(Exception):", tag="E6")
    else:
        c.add(f"class {cls}(LaminaError):")
    c.add(f'    """Raised for {n.replace("_", " ")} problems."""')
    c.add("")
    c.add("")
    c.add(_sig(f, fn, [("message", "str", None), ("line", "int", None), ("column", "int", None), ("*", "", None),
                      _skip_param(f)], "None"))
    _doc(f, c, f"Raise {cls} for message at line and column.")
    _skip_body(f, c, "message")
    msg = _var(f, "full_message")
    c.add(f'    {msg} = message if message.endswith(".") else message + "."')
    c.add("    if line < 1:")
    if f.on("E6"):
        c.add(f"        raise {cls}({msg})")
    else:
        c.add(f"        raise {cls}({msg}, 1, max(column, 1))")
    if f.on("E6"):
        c.add(f"    raise {cls}({msg})")
    else:
        c.add(f"    raise {cls}({msg}, line, column)")
    tests = None
    tpath = f"tests/test_errors_{n}.py"
    if f.with_tests and not f.on("S1"):
        tests = (f"import pytest\n\nfrom {pkg}.diagnostics.{n} import {cls}, {fn}\n\n\n"
                 f"def test_{n}_raises():\n    with pytest.raises({cls}):\n        {fn}(\"bad\", 2, 3)\n\n\n"
                 f"def test_{n}_line_zero():\n    with pytest.raises({cls}):\n        {fn}(\"bad\", 0, 0)\n")
    return Rendered({mod: c.text(), **({tpath: tests} if tests else {})}, {k: (mod, v) for k, v in c.tags.items()},
                    fn, mod, tpath if tests else None, ["message", "line", "column", "skip"], cls, 2)


def _cli(f: Feature) -> Rendered:
    pkg, n = f.pkg, f.noun
    fn = f"cmd_{n}"
    mod = f"{pkg}/cli/{n}.py"
    c = _Code()
    c.add(f'"""`lamina {n.replace("_", "-")}`: print information about a config file."""')
    c.add("")
    if f.on("S2") and _h(n) % 2:
        c.add("import os")
    c.add("import sys")
    c.add("")
    c.add(f"from {pkg}.parser import parse")
    c.add("")
    c.add("")
    c.add(_sig(f, fn, [("argv", "list[str]", None), ("*", "", None), _skip_param(f)], "int"))
    _doc(f, c, f"Run the {n.replace('_', ' ')} command; return the exit code.")
    _skip_body(f, c, "\"--\"")
    if f.on("S4") and _h(n) % 2 == 0:
        pass
    c.add("    if len(argv) != 1:")
    c.add(f'        print("usage: lamina {n.replace("_", "-")} FILE", file=sys.stderr)')
    c.add("        return 2")
    txt = _var(f, "source_text")
    if f.on("B1"):
        c.add("    with open(argv[0]) as fh:", tag="B1")
    else:
        c.add('    with open(argv[0], encoding="utf-8") as fh:')
    c.add(f"        {txt} = fh.read()")
    c.add(f"    doc = parse({txt}, source=argv[0])")
    c.add("    for section in doc.sections():")
    c.add('        print(f"{section.name}: {len(section.entries())}")')
    c.add("    return 0")
    tests = None
    tpath = f"tests/test_cli_{n}.py"
    if f.with_tests and not f.on("S1"):
        tests = (f"from {pkg}.cli.{n} import {fn}\n\n\n"
                 f"def test_{n}_counts(write, capsys):\n    path = write(\"c_{n}.conf\", \"[a]\\nx = 1\\ny = 2\\n\")\n"
                 f"    assert {fn}([path]) == 0\n    assert capsys.readouterr().out.strip() == \"a: 2\"\n\n\n"
                 f"def test_{n}_usage():\n    assert {fn}([]) == 2\n")
    return Rendered({mod: c.text(), **({tpath: tests} if tests else {})}, {k: (mod, v) for k, v in c.tags.items()},
                    fn, mod, tpath if tests else None, ["argv", "skip"], "LaminaError", 2)


ARCHETYPES = {"include": _include, "interpolate": _interpolate, "lexer": _lexer, "parser": _parser,
              "model": _model, "dump": _dump, "loader": _loader, "errors": _errors, "cli": _cli}
CODE_AREAS = tuple(ARCHETYPES)
# Slots each archetype can carry (others are ignored for that area).
AREA_SLOTS = {
    "include": {"E1", "E6", "B1", "B2", "T3", "S1", "S2", "S3", "S4"},
    "interpolate": {"E8", "E6", "S1", "S2", "S3", "S4"},
    "lexer": {"E4", "S1", "S2", "S3", "S4", "E3"},
    "parser": {"E6", "S1", "S2", "S3", "S4"},
    "model": {"E2", "E7", "D1", "S1", "S2", "S3", "S4"},
    "dump": {"E2", "E7", "D1", "S1", "S2", "S3", "S4"},
    "loader": {"E5", "E7", "B1", "B2", "D1", "S1", "S2", "S3", "S4"},
    "errors": {"E6", "S1", "S2", "S3", "S4"},
    "cli": {"B1", "S1", "S2", "S3", "S4"},
}
# Keyword parameters E7 may rename (old → new), per area.
RENAMES = {"loader": {"strict": "check"}, "model": {"create": "add_missing"}, "dump": {"indent": "width"}}


_CAMEL_ASSIGN = re.compile(r"^\s*([a-z]+[A-Z][A-Za-z]+)(: [^=]+)? = ")


def render(f: Feature) -> Rendered:
    """Render a feature and locate every planted slot (path, 1-based line in the new file)."""
    r = ARCHETYPES[f.area](f)
    text = r.files[r.module_path]
    lines = text.splitlines()
    def_line = next((i for i, ln in enumerate(lines, 1) if ln.startswith(f"def {r.fn}(")), 1)
    for slot in ("S1", "S3", "D1", "E7"):
        if f.on(slot) or (slot == "E7" and f.renames and not f.deprecated):
            r.locations.setdefault(slot, (r.module_path, def_line))
    r.locations["def"] = (r.module_path, def_line)
    if f.on("S2"):
        for i, ln in enumerate(lines, 1):
            if _CAMEL_ASSIGN.match(ln) or ln.strip() == "import sys" or (ln.strip() == "import os" and f.area == "cli"):
                r.locations["S2"] = (r.module_path, i)
                break
    return r
