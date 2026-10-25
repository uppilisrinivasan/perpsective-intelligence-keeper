import os

import pytest

from lamina.errors import IncludeError
from lamina.include import MAX_DEPTH, resolve_include
from lamina.loader import load


def test_include_merges_values(write, tmp_path):
    write("base.conf", "[db]\nhost = base\nport = 1\n")
    path = write("app.conf", '@include "base.conf"\n[db]\nport = 2\n')
    doc = load(path)
    assert doc.get("db.host") == "base"
    assert doc.get("db.port") == "2"


def test_nested_include_from_subdirectory(write, tmp_path):
    write("shared/common.conf", "[a]\nx = shared\n")
    path = write("sub/app.conf", '@include "../shared/common.conf"\n[b]\ny = 1\n')
    assert load(path, root=str(tmp_path)).get("a.x") == "shared"


def test_escape_with_dotdot_is_rejected(write, tmp_path):
    write("outside.conf", "[a]\nx = 1\n")
    write("proj/app.conf", '@include "../outside.conf"\n')
    with pytest.raises(IncludeError) as e:
        load(str(tmp_path / "proj" / "app.conf"))
    assert "escapes" in str(e.value)


def test_symlink_escape_is_rejected(write, tmp_path):
    write("secret/keys.conf", "[k]\nv = 1\n")
    (tmp_path / "proj").mkdir()
    os.symlink(tmp_path / "secret", tmp_path / "proj" / "link")
    with pytest.raises(IncludeError):
        resolve_include(str(tmp_path / "proj"), "link/keys.conf", str(tmp_path / "proj"))


def test_missing_include(write, tmp_path):
    path = write("app.conf", '@include "nope.conf"\n')
    with pytest.raises(IncludeError) as e:
        load(path)
    assert "not found" in str(e.value)


def test_cycle_detected(write, tmp_path):
    write("a.conf", '@include "b.conf"\n')
    path = write("b.conf", '@include "a.conf"\n')
    with pytest.raises(IncludeError):
        load(path)


def test_depth_limit(write, tmp_path):
    for i in range(MAX_DEPTH + 3):
        write(f"c{i}.conf", f'@include "c{i + 1}.conf"\n')
    write(f"c{MAX_DEPTH + 3}.conf", "[end]\nk = v\n")
    with pytest.raises(IncludeError) as e:
        load(str(tmp_path / "c0.conf"))
    assert "deeper" in str(e.value)
