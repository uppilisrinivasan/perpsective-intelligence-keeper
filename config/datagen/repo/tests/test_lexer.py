import pytest

from lamina.errors import ParseError
from lamina.lexer import tokenize


def kinds(text):
    return [t.kind for t in tokenize(text)]


def test_entry_and_section():
    assert kinds("[a]\nx = 1\n") == ["SECTION", "ENTRY"]


def test_blank_and_comment_lines():
    assert kinds("# top\n\n; also\n") == ["COMMENT", "BLANK", "COMMENT"]


def test_include_directive():
    tok = tokenize('@include "base.conf"')[0]
    assert (tok.kind, tok.value) == ("INCLUDE", "base.conf")


def test_inline_comment_is_kept_separately():
    tok = tokenize("x = 1  # one")[0]
    value, _, note = tok.extra.partition("\x00")
    assert (value, note) == ("1", "# one")


def test_hash_inside_quotes_is_not_a_comment():
    tok = tokenize('x = "a # b"')[0]
    assert tok.extra == '"a # b"'


def test_positions_are_one_based():
    tok = tokenize("\n  [s]")[1]
    assert (tok.line, tok.column) == (2, 3)


def test_bad_section_header():
    with pytest.raises(ParseError) as e:
        tokenize("[oops")
    assert e.value.line == 1


def test_unparseable_line_reports_position():
    with pytest.raises(ParseError) as e:
        tokenize("[a]\nnot a pair")
    assert (e.value.line, e.value.column) == (2, 1)


def test_missing_key():
    with pytest.raises(ParseError):
        tokenize("= 3")
