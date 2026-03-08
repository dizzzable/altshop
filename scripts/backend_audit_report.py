from __future__ import annotations

import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import TypedDict

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

ERROR_RE = re.compile(
    r"^(?P<file>[^:]+\.py):\d+(?::\d+)?: error: .*?(?:\[(?P<code>[^\]]+)\])?$"
)
IGNORED_PARTS = {
    ".git",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    ".idea",
    "node_modules",
    "dist",
    "venv",
}
TEXT_SUFFIXES = {".md", ".py"}


def _is_ignored_path(path: Path) -> bool:
    if any(part in IGNORED_PARTS for part in path.parts):
        return True

    parts = path.parts
    return "docs" in parts and "archive" in parts


class RuntimeCompatibilityCheck(TypedDict):
    description: str
    paths: tuple[str, ...]
    patterns: tuple[str, ...]


class RuntimeCompatibilityResult(TypedDict):
    description: str
    paths: list[str]


PAYMENT_COMPATIBILITY_CODE_CHECKS: dict[str, RuntimeCompatibilityCheck] = {
    "heleket_provider_legacy_fallback": {
        "description": "Heleket legacy provider fallback remains in runtime",
        "paths": ("src/infrastructure/payment_gateways/heleket.py",),
        "patterns": ("_create_payment_legacy(", "legacy_fallback", "_build_legacy_auth_headers("),
    },
    "platega_webhook_legacy_payload": {
        "description": "Platega legacy payload webhook parser remains in runtime",
        "paths": ("src/infrastructure/payment_gateways/platega.py",),
        "patterns": ('"legacy_payload"', '"legacy_no_headers"'),
    },
    "pal24_legacy_json_contract": {
        "description": "Pal24 legacy JSON contract remains in runtime",
        "paths": ("src/infrastructure/payment_gateways/pal24.py",),
        "patterns": ('"legacy_fallback"', '"legacy_json"', "_create_bill_legacy("),
    },
}


def _repo_root() -> Path:
    return REPO_ROOT


def _run_mypy(repo_root: Path) -> tuple[int, Counter[str], Counter[str]]:
    process = subprocess.run(
        [sys.executable, "-m", "mypy", "src", "--hide-error-context", "--no-color-output"],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    output = "\n".join(part for part in (process.stdout, process.stderr) if part)
    file_counts: Counter[str] = Counter()
    code_counts: Counter[str] = Counter()

    for line in output.splitlines():
        match = ERROR_RE.match(line.strip())
        if not match:
            continue
        file_counts[match.group("file").replace("\\", "/")] += 1
        code_counts[match.group("code") or "no-code"] += 1

    return process.returncode, file_counts, code_counts


def _iter_text_files(repo_root: Path) -> list[Path]:
    files: list[Path] = []
    for path in repo_root.rglob("*"):
        if not path.is_file():
            continue
        if path.suffix not in TEXT_SUFFIXES:
            continue
        if _is_ignored_path(path):
            continue
        files.append(path)
    return files


def _scan_auth_username(repo_root: Path) -> dict[str, list[str]]:
    categories: dict[str, list[str]] = {
        "runtime": [],
        "migrations": [],
        "tests": [],
        "docs": [],
        "tooling": [],
        "other": [],
    }
    for path in _iter_text_files(repo_root):
        try:
            contents = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            contents = path.read_text(encoding="utf-8", errors="ignore")
        if "auth_username" not in contents:
            continue

        relative = path.relative_to(repo_root).as_posix()
        if relative.startswith("src/infrastructure/database/migrations/"):
            categories["migrations"].append(relative)
        elif relative.startswith("src/"):
            categories["runtime"].append(relative)
        elif relative.startswith("tests/"):
            categories["tests"].append(relative)
        elif relative.startswith("docs/"):
            categories["docs"].append(relative)
        elif relative.startswith("scripts/"):
            categories["tooling"].append(relative)
        else:
            categories["other"].append(relative)

    return {category: sorted(paths) for category, paths in categories.items() if paths}


def _scan_compatibility_code_presence(
    repo_root: Path,
    checks: dict[str, RuntimeCompatibilityCheck],
) -> dict[str, RuntimeCompatibilityResult]:
    results: dict[str, RuntimeCompatibilityResult] = {}
    for key, check in checks.items():
        matched_paths: list[str] = []
        for relative in check["paths"]:
            path = repo_root / relative
            if not path.is_file():
                continue
            try:
                contents = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                contents = path.read_text(encoding="utf-8", errors="ignore")
            if all(pattern in contents for pattern in check["patterns"]):
                matched_paths.append(relative)

        if matched_paths:
            results[key] = {
                "description": check["description"],
                "paths": matched_paths,
            }
    return results


def _write(line: str = "") -> None:
    sys.stdout.write(f"{line}\n")


def _print_counter(title: str, counter: Counter[str], limit: int) -> None:
    _write(title)
    for name, count in counter.most_common(limit):
        _write(f"- {name}: {count}")


def _print_auth_compatibility_section(
    auth_compatibility: dict[str, RuntimeCompatibilityResult],
) -> None:
    _write()
    _write("## Auth compatibility surface")
    if not auth_compatibility:
        _write("- none detected")
    for key, payload in auth_compatibility.items():
        _write(f"- {key}: {payload['description']}")
        for path in payload["paths"]:
            _write(f"  - {path}")


def _print_payment_compatibility_section(
    payment_compatibility_code: dict[str, RuntimeCompatibilityResult],
) -> None:
    _write()
    _write("## Payment compatibility code present")
    if not payment_compatibility_code:
        _write("- none detected")
    for key, payload in payment_compatibility_code.items():
        _write(f"- {key}: {payload['description']}")
        for path in payload["paths"]:
            _write(f"  - {path}")


def main() -> int:
    repo_root = _repo_root()
    mypy_exit_code, file_counts, code_counts = _run_mypy(repo_root)
    auth_username_paths = _scan_auth_username(repo_root)
    auth_compatibility: dict[str, RuntimeCompatibilityResult] = {}
    payment_compatibility_code = _scan_compatibility_code_presence(
        repo_root,
        PAYMENT_COMPATIBILITY_CODE_CHECKS,
    )

    _write("# Backend Audit Report")
    _write()
    _write("## Typing")
    _write(f"- mypy exit code: {mypy_exit_code}")
    _write(f"- total errors: {sum(file_counts.values())}")
    _write(f"- files with errors: {len(file_counts)}")
    _print_counter("- top files:", file_counts, limit=8)
    _print_counter("- top error codes:", code_counts, limit=8)
    _write()
    _write("## Legacy auth marker: auth_username")
    _write(
        "- note: `password_hash` is not used as the primary marker here because "
        "`web_accounts.password_hash` is still an active, non-legacy field."
    )
    for category in ("runtime", "migrations", "tests", "docs", "tooling", "other"):
        paths = auth_username_paths.get(category)
        if not paths:
            continue
        _write(f"- {category}: {len(paths)}")
        for path in paths:
            _write(f"  - {path}")

    _print_auth_compatibility_section(auth_compatibility)
    _print_payment_compatibility_section(payment_compatibility_code)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
