from __future__ import annotations

import argparse
import re
from pathlib import Path

HEADER_RE = re.compile(
    r"^## \[(?P<version>[^\]]+)\](?: - (?P<date>\d{4}-\d{2}-\d{2}))?\s*$",
    re.MULTILINE,
)


def _extract_changelog_section(changelog: str, version: str) -> tuple[str, str]:
    matches = list(HEADER_RE.finditer(changelog))
    for index, match in enumerate(matches):
        if match.group("version") != version:
            continue

        section_start = match.end()
        section_end = matches[index + 1].start() if index + 1 < len(matches) else len(changelog)
        title = match.group(0).strip()
        body = changelog[section_start:section_end].strip()
        if not body:
            raise ValueError(f"Changelog section {title!r} is empty.")
        return title, body

    raise ValueError(f"Version {version!r} was not found in CHANGELOG.md.")


def _render_template(template: str, replacements: dict[str, str]) -> str:
    rendered = template
    for key, value in replacements.items():
        rendered = rendered.replace(f"{{{{ {key} }}}}", value)
    return rendered


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build release notes from a changelog section and a template."
    )
    parser.add_argument("--version", required=True, help="Release version without the v prefix.")
    parser.add_argument("--tag", required=True, help="Release tag, for example v1.0.0.")
    parser.add_argument("--changelog", required=True, help="Path to CHANGELOG.md.")
    parser.add_argument("--template", required=True, help="Path to the release notes template.")
    parser.add_argument("--output", required=True, help="Path to the rendered release notes file.")
    args = parser.parse_args()

    changelog_text = Path(args.changelog).read_text(encoding="utf-8")
    template_text = Path(args.template).read_text(encoding="utf-8")

    changelog_title, changelog_section = _extract_changelog_section(
        changelog_text,
        args.version,
    )

    rendered = _render_template(
        template_text,
        {
            "VERSION": args.version,
            "TAG": args.tag,
            "CHANGELOG_TITLE": changelog_title,
            "CHANGELOG_SECTION": changelog_section,
        },
    ).strip()

    Path(args.output).write_text(f"{rendered}\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
