import pytest

from lamina.errors import InterpolationError
from lamina.interpolate import interpolate
from lamina.loader import loads


def test_simple_reference():
    assert interpolate("${HOME}/x", {"HOME": "/h"}) == "/h/x"


def test_default_used_when_missing():
    assert interpolate("${PORT:-8080}", {}) == "8080"


def test_empty_value_uses_default():
    assert interpolate("${PORT:-8080}", {"PORT": ""}) == "8080"


def test_undefined_raises_with_name_only():
    with pytest.raises(InterpolationError) as e:
        interpolate("${TOKEN}", {})
    assert "TOKEN" in str(e.value)


def test_error_never_contains_env_values():
    with pytest.raises(InterpolationError) as e:
        interpolate("${A}${", {"A": "s3cr3t-value"})
    assert "s3cr3t-value" not in str(e.value)


def test_invalid_name():
    with pytest.raises(InterpolationError):
        interpolate("${bad-name}", {})


def test_document_interpolation():
    doc = loads("[a]\nurl = http://${HOST:-localhost}\n", env={})
    assert doc.get("a.url") == "http://localhost"


def test_strict_requires_env():
    with pytest.raises(InterpolationError):
        loads("[a]\nx = ${Y}\n")
