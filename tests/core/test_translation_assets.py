from pathlib import Path

MOJIBAKE_FRAGMENTS = (
    "\u0432\u0402\u045e",
    "\u0440\u045f",
)
REPO_MOJIBAKE_FRAGMENTS = (
    "РЎ",
    "Рџ",
    "Рќ",
    "Р”",
    "СЃ",
    "С‚",
    "СЊ",
    "вЂ",
    "вќ",
    "рџ",
    "пёЏ",
)
TEXT_SUFFIXES = {".py", ".ftl", ".ts", ".tsx", ".js", ".jsx", ".css", ".md", ".mjs"}
SKIP_DIR_NAMES = {
    ".git",
    ".venv",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "__pycache__",
    "node_modules",
    "dist",
}
ALLOWED_FILES = {
    Path("tests/core/test_translation_assets.py"),
    Path("tests/core/test_main_menu_render.py"),
    Path("tests/core/test_runtime_localization_guards.py"),
    Path("web-app/scripts/check-mojibake.mjs"),
}
SCAN_TARGETS = (
    Path("src"),
    Path("tests"),
    Path("assets/translations"),
    Path("web-app/src"),
    Path("web-app/scripts"),
    Path("web-app/AUTH_SYSTEM.md"),
    Path("web-app/LANDING_PAGE.md"),
)


def _iter_repo_text_files() -> list[Path]:
    files: list[Path] = []

    for target in SCAN_TARGETS:
        if not target.exists():
            continue
        if target.is_file():
            if target.suffix in TEXT_SUFFIXES and target not in ALLOWED_FILES:
                files.append(target)
            continue

        for path in sorted(target.rglob("*")):
            if not path.is_file():
                continue
            if any(part in SKIP_DIR_NAMES for part in path.parts):
                continue
            if path.suffix not in TEXT_SUFFIXES or path in ALLOWED_FILES:
                continue
            files.append(path)

    return files


def test_bot_translation_assets_do_not_contain_known_mojibake_fragments() -> None:
    translation_root = Path("assets/translations")
    hits: list[str] = []

    for ftl_path in sorted(translation_root.rglob("*.ftl")):
        text = ftl_path.read_text(encoding="utf8")
        for line_number, line in enumerate(text.splitlines(), start=1):
            for fragment in MOJIBAKE_FRAGMENTS:
                if fragment in line:
                    escaped_line = line.encode("unicode_escape").decode("ascii")
                    hits.append(f"{ftl_path}:{line_number}: {escaped_line}")
                    break

    assert hits == []


def test_repo_text_assets_do_not_contain_known_mojibake_fragments() -> None:
    hits: list[str] = []

    for file_path in _iter_repo_text_files():
        text = file_path.read_text(encoding="utf8")
        for line_number, line in enumerate(text.splitlines(), start=1):
            for fragment in REPO_MOJIBAKE_FRAGMENTS:
                if fragment in line:
                    escaped_line = line.encode("unicode_escape").decode("ascii")
                    hits.append(f"{file_path}:{line_number}: {escaped_line}")
                    break

    assert hits == []
