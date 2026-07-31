import importlib
import sys

import pytest


class _BlockFastAPIImport:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "fastapi":
            raise ModuleNotFoundError("No module named 'fastapi'")
        return None


def test_main_app_fails_fast_when_fastapi_is_not_installed():
    sys.modules.pop("backend.app.main", None)
    sys.modules.pop("backend.app.api.v1.health", None)
    blocker = _BlockFastAPIImport()
    sys.meta_path.insert(0, blocker)

    try:
        with pytest.raises(RuntimeError, match="FastAPI is not installed"):
            importlib.import_module("backend.app.main")
    finally:
        sys.meta_path.remove(blocker)
        sys.modules.pop("backend.app.main", None)
        sys.modules.pop("backend.app.api.v1.health", None)
