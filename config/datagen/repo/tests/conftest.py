import pytest


@pytest.fixture
def write(tmp_path):
    def _write(name: str, text: str) -> str:
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return str(path)

    return _write
