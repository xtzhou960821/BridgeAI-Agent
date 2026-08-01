import importlib
import sys

import pytest


class _BlockFastAPIImport:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "fastapi":
            raise ModuleNotFoundError("No module named 'fastapi'")
        return None


def test_main_app_fails_fast_when_fastapi_is_not_installed():
    module_names = [
        name
        for name in sys.modules
        if name in {
            "backend.app.main",
            "backend.app.api.v1.health",
            "backend.app.api.v1.tasks",
            "fastapi",
        }
        or name.startswith("fastapi.")
    ]
    cached_modules = {name: sys.modules.pop(name) for name in module_names}
    blocker = _BlockFastAPIImport()
    sys.meta_path.insert(0, blocker)

    try:
        with pytest.raises(RuntimeError, match="FastAPI is not installed"):
            importlib.import_module("backend.app.main")
    finally:
        sys.meta_path.remove(blocker)
        for name in module_names:
            sys.modules.pop(name, None)
        sys.modules.update(cached_modules)
