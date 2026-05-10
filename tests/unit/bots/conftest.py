import sys
import pytest


@pytest.fixture(autouse=True, scope="module")
def real_bots_imports():
    """Remove bots mocks for this module so real bots code can be imported and tested.
    Restores the mocks afterward so other unit tests are unaffected."""
    bots_keys = [k for k in sys.modules if k == "bots" or k.startswith("bots.")]
    saved = {k: sys.modules.pop(k) for k in bots_keys}
    yield
    sys.modules.update(saved)
