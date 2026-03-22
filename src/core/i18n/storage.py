from __future__ import annotations

from pathlib import Path
from typing import Iterable

from fluent_compiler.bundle import FluentBundle  # type: ignore[import-untyped]
from fluentogram.exceptions import LocalesNotFoundError
from fluentogram.storage.base import BaseStorage
from fluentogram.translator import FluentTranslator


class OverlayFileStorage(BaseStorage):
    """Load translations from multiple directories with first-source priority."""

    def __init__(
        self,
        *paths: str | Path,
        use_isolating: bool = False,
    ) -> None:
        super().__init__()
        self.paths = tuple(Path(path) for path in paths if path)
        self.use_isolating = use_isolating
        self._load_translations()

    @staticmethod
    def _normalize_root(path: Path) -> Path:
        if "{locale}" in path.parts:
            return Path(*path.parts[: path.parts.index("{locale}")])
        return path

    @staticmethod
    def _resolve_locale_dir(path: Path, locale: str) -> Path:
        if "{locale}" not in path.as_posix():
            path = path / "{locale}"
        return Path(path.as_posix().format(locale=locale))

    def _extract_locales(self) -> list[str]:
        locales: set[str] = set()

        for path in self.paths:
            root = self._normalize_root(path)
            if not root.exists():
                continue
            locales.update(file_path.name for file_path in root.iterdir() if file_path.is_dir())

        if not locales:
            search_root = self.paths[0] if self.paths else Path(".")
            raise LocalesNotFoundError(
                locales=[],
                path=self._normalize_root(search_root).as_posix(),
            )

        return sorted(locales)

    def _find_locale_files(self, locale: str) -> Iterable[Path]:
        seen_paths: set[Path] = set()

        for path in self.paths:
            locale_dir = self._resolve_locale_dir(path, locale)
            if not locale_dir.exists():
                continue

            for file_path in sorted(locale_dir.rglob("*.ftl")):
                resolved_path = file_path.resolve()
                if resolved_path in seen_paths:
                    continue

                seen_paths.add(resolved_path)
                yield file_path

    def _load_translations(self) -> None:
        for locale in self._extract_locales():
            texts = [path.read_text(encoding="utf8") for path in self._find_locale_files(locale)]
            if not texts:
                continue

            self.add_translator(
                FluentTranslator(
                    locale=locale,
                    translator=FluentBundle.from_string(
                        text="\n".join(texts),
                        locale=locale,
                        use_isolating=self.use_isolating,
                    ),
                )
            )

    async def close(self) -> None:
        pass
