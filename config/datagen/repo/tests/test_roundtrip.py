import pytest

from lamina.dump import dumps
from lamina.parser import parse

SAMPLES = [
    "[a]\nx = 1\n",
    "# header\n\n[server]\nhost = 0.0.0.0   # all interfaces\nport = 8080\n\n[log]\nlevel = info\n",
    "[b]\nz = 26\na = 1\nm = 13\n",
    "; semicolon comment\n[s]\n\n\nk = v\n",
    '[q]\nmsg = "hello # not a comment"\n',
    '@include "base.conf"\n[app]\nname = demo\n',
]


@pytest.mark.parametrize("text", SAMPLES)
def test_round_trip_is_exact(text):
    assert dumps(parse(text)) == text


def test_key_order_is_preserved():
    text = "[b]\nz = 26\na = 1\nm = 13\n"
    assert parse(text).section("b").keys() == ["z", "a", "m"]
