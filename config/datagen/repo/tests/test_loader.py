import pytest

from lamina import LaminaError, load, loads
from lamina.dump import dumps


def test_load_file(write):
    path = write("c.conf", "[a]\nx = 1\n")
    assert load(path).get("a.x") == "1"


def test_load_sets_source(write):
    path = write("c.conf", "[a]\nx = 1\n")
    assert load(path).source == path


def test_loads_round_trip():
    text = "# c\n[a]\nx = 1\n"
    assert dumps(loads(text)) == text


def test_non_strict_keeps_references():
    assert loads("[a]\nx = ${Y}\n", strict=False).get("a.x") == "${Y}"


def test_utf8_values(write):
    path = write("u.conf", "[a]\nname = Zoë\n")
    assert load(path).get("a.name") == "Zoë"


def test_errors_are_lamina_errors():
    with pytest.raises(LaminaError):
        loads("[a\n")
