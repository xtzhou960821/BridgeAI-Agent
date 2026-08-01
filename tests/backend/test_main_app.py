import importlib
import sys

import pytest


class _BlockFastAPIImport:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "fastapi":
            raise ModuleNotFoundError("No module named 'fastapi'")
        return None


def test_main_app_fails_fast_when_fastapi_is_not_installed():
    importlib.import_module("backend.app.main")
    backend_package = importlib.import_module("backend.app")
    api_package = importlib.import_module("backend.app.api.v1")
    cached_parent_attributes = {
        (backend_package, "main"): backend_package.main,
        (api_package, "health"): api_package.health,
        (api_package, "tasks"): api_package.tasks,
        (api_package, "artifacts"): api_package.artifacts,
    }
    module_names = [
        name
        for name in sys.modules
        if name in {
            "backend.app.main",
            "backend.app.api.v1.health",
            "backend.app.api.v1.tasks",
            "backend.app.api.v1.artifacts",
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
        for (parent_module, attribute), value in cached_parent_attributes.items():
            setattr(parent_module, attribute, value)

    assert backend_package.main is sys.modules["backend.app.main"]
    assert api_package.health is sys.modules["backend.app.api.v1.health"]
    assert api_package.tasks is sys.modules["backend.app.api.v1.tasks"]
    assert api_package.artifacts is sys.modules["backend.app.api.v1.artifacts"]
