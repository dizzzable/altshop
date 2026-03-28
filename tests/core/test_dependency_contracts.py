from __future__ import annotations

import tomllib
from pathlib import Path

from packaging.requirements import Requirement

REPO_ROOT = Path(__file__).resolve().parents[2]


def _normalize_dependency(raw_dependency: str) -> tuple[str, tuple[str, ...], str, str | None]:
    requirement = Requirement(raw_dependency)
    return (
        requirement.name,
        tuple(sorted(requirement.extras)),
        str(requirement.specifier),
        requirement.url,
    )


def _read_pyproject_dependencies() -> dict[str, tuple[str, tuple[str, ...], str, str | None]]:
    pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dependencies: list[str] = pyproject["project"]["dependencies"]
    return {
        Requirement(dependency).name: _normalize_dependency(dependency)
        for dependency in dependencies
    }


def _read_requirements_dependencies() -> dict[str, tuple[str, tuple[str, ...], str, str | None]]:
    requirements_path = REPO_ROOT / "requirements.txt"
    dependencies: dict[str, tuple[str, tuple[str, ...], str, str | None]] = {}
    for raw_line in requirements_path.read_text(encoding="utf-8").splitlines():
        stripped_line = raw_line.split("#", 1)[0].strip()
        if not stripped_line:
            continue
        normalized_dependency = _normalize_dependency(stripped_line)
        dependencies[normalized_dependency[0]] = normalized_dependency
    return dependencies


def test_requirements_dependencies_match_pyproject() -> None:
    assert _read_requirements_dependencies() == _read_pyproject_dependencies()
