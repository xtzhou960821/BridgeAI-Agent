import tomllib
from pathlib import Path


def test_pyproject_limits_setuptools_discovery_to_python_packages():
    config = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    package_finder = config["tool"]["setuptools"]["packages"]["find"]

    assert package_finder["include"] == ["agent*", "backend*", "tools*"]
    assert "frontend*" in package_finder["exclude"]
    assert "docs*" in package_finder["exclude"]
    assert "tests*" in package_finder["exclude"]


def test_pyproject_declares_upload_image_dependencies_for_the_backend():
    config = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    backend_dependencies = config["project"]["optional-dependencies"]["backend"]

    assert any(dependency.startswith("pillow>=11") for dependency in backend_dependencies)
    assert any(
        dependency.startswith("python-multipart>=0.0.9")
        for dependency in backend_dependencies
    )
