from pathlib import Path

MOJIBAKE_FRAGMENTS = (
    "\u0432\u0402\u045e",
    "\u0440\u045f",
)


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
