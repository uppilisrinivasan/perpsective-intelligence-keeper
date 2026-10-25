import pathlib

from lamina import loads

DATA = pathlib.Path(__file__).parent / "data"


def test_text_fixture_parses():
    assert loads((DATA / "sample.conf").read_text(encoding="utf-8")).get("server.port") == "8080"
