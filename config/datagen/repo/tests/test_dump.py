import io

from lamina.dump import dump, dumps
from lamina.model import Document, Entry, Section
from lamina.parser import parse


def test_new_entry_format():
    doc = Document(sections_=[Section("a", [Entry("x", "1")])])
    assert dumps(doc) == "[a]\nx = 1\n"


def test_changed_value_rewrites_only_that_line():
    doc = parse("[a]\nx   =   1\ny = 2\n")
    doc.section("a").set("y", "3")
    assert dumps(doc) == "[a]\nx   =   1\ny = 3\n"


def test_note_is_kept_on_new_lines():
    doc = Document(sections_=[Section("a", [Entry("x", "1", note="# why")])])
    assert dumps(doc) == "[a]\nx = 1  # why\n"


def test_dump_to_file():
    buf = io.StringIO()
    dump(parse("[a]\nx = 1\n"), buf)
    assert buf.getvalue() == "[a]\nx = 1\n"


def test_empty_document():
    assert dumps(Document()) == ""
