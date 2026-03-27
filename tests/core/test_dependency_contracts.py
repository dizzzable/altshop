from __future__ import annotations

import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _read_pyproject_dependency(package_name: str) -> str:
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies: list[str] = pyproject["project"]["dependencies"]
    return next(
        dependency
        for dependency in dependencies
        if dependency.startswith(f"{package_name}>=") or dependency.startswith(f"{package_name}==")
    )


def _read_requirements_dependency(package_name: str) -> str:
    requirements_path = REPO_ROOT / "requirements.txt"
    for raw_line in requirements_path.read_text(encoding="utf-8").splitlines():
        stripped_line = raw_line.split("#", 1)[0].strip()
        if not stripped_line:
            continue
        if stripped_line.startswith(f"{package_name}>=") or stripped_line.startswith(
            f"{package_name}=="
        ):
            return stripped_line
    raise AssertionError(f"Could not find {package_name!r} in requirements.txt")


def test_requirements_remnawave_constraint_matches_pyproject() -> None:
    assert _read_requirements_dependency("remnawave") == _read_pyproject_dependency("remnawave")
