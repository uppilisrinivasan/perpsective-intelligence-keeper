from lamina.errors import IncludeError, InterpolationError, LaminaError, ParseError


def test_str_has_position():
    assert str(ParseError("bad", 3, 7)) == "bad (line 3, column 7)"


def test_hierarchy():
    for cls in (ParseError, IncludeError, InterpolationError):
        assert issubclass(cls, LaminaError)


def test_attributes():
    e = IncludeError("x", 1, 2)
    assert (e.message, e.line, e.column) == ("x", 1, 2)
