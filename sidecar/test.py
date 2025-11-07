import pytest
from sidecar.Sidecar import *
from sidecar.helpers import *

# Run `pytest -v``
def test_ensure_type_accepts_expected_type():
    assert ensure_type({"a": 1}, dict) == {"a": 1}

def test_ensure_type_accepts_multiple_types():
    assert ensure_type(3.14, (int, float)) == 3.14

def test_ensure_type_raises_for_wrong_type():
    with pytest.raises(TypeError) as exc:
        ensure_type("hello", int, name="age")
    assert "age must be of type int" in str(exc.value)