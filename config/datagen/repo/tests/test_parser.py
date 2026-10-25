import pytest

from lamina.errors import ParseError
from lamina.parser import parse


def test_sections_and_values():
    doc = parse("[db]\nhost = localhost\nport = 5432\n")
    assert doc.get("db.host") == "localhost"
    assert doc.get("db.port") == "5432"


def test_preamble_comments():
    doc = parse("# config\n\n[a]\nx = 1\n")
    assert len(doc.preamble) == 2


def test_duplicate_section_rejected():
    with pytest.raises(ParseError) as e:
        parse("[a]\n[a]\n")
    assert e.value.line == 2


def test_duplicate_key_rejected():
    with pytest.raises(ParseError):
        parse("[a]\nx = 1\nx = 2\n")


def test_entry_outside_section():
    with pytest.raises(ParseError) as e:
        parse("x = 1\n")
    assert "outside" in str(e.value)


def test_includes_are_collected():
    doc = parse('@include "a.conf"\n[s]\nk = v\n')
    assert doc.includes == ["a.conf"]


def test_missing_value_is_empty_string():
    assert parse("[a]\nx =\n").get("a.x") == ""


def test_error_message_has_position():
    with pytest.raises(ParseError) as e:
        parse("[a]\n[b\n")
    assert "line 2" in str(e.value)
