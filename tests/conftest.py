import json
from importlib.resources import files
import pytest

@pytest.fixture
def sample():
    return json.loads(files("ss_assembly").joinpath("fixtures/demo.json").read_text(encoding="utf-8"))
