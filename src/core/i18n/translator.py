from typing import Any

from fluentogram import TranslatorRunner
from fluentogram.exceptions import KeyNotFoundError
from loguru import logger

I18N_FALLBACK_PREFIXES = {"btn", "msg", "ntf", "hdr", "frg"}
I18N_FALLBACK_EMOJIS = {
    "btn": "🔘",
    "msg": "📝",
    "ntf": "⚠️",
    "hdr": "🏷️",
    "frg": "🧩",
}


def humanize_i18n_key(key: str) -> str:
    if not key:
        return key

    normalized_key = key.replace("_", "-")
    parts = [part for part in normalized_key.split("-") if part]

    if parts and parts[0] in I18N_FALLBACK_PREFIXES:
        parts = parts[1:]

    if not parts:
        return key

    return " ".join(part.capitalize() for part in parts)


def build_i18n_fallback(key: str) -> str:
    label = humanize_i18n_key(key)
    if not key:
        return label

    normalized_key = key.replace("_", "-")
    prefix = next((part for part in normalized_key.split("-") if part), "")
    emoji = I18N_FALLBACK_EMOJIS.get(prefix)

    if not emoji:
        return label

    return f"{emoji} {label}"


def safe_i18n_get(i18n: TranslatorRunner, key: str, **kwargs: Any) -> str:
    if not key:
        return key

    try:
        return i18n.get(key, **kwargs)
    except KeyNotFoundError:
        fallback = build_i18n_fallback(key)
        logger.warning(
            f"Translation key '{key}' not found. Falling back to generated label '{fallback}'"
        )
        return fallback


def get_translated_kwargs(i18n: TranslatorRunner, kwargs: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}

    for k, v in kwargs.items():
        # case ("key", {"value": 5})
        if (
            isinstance(v, tuple)
            and len(v) == 2
            and isinstance(v[0], str)
            and isinstance(v[1], dict)
        ):
            key, sub_kwargs = v
            processed_sub_kwargs = get_translated_kwargs(i18n, sub_kwargs)
            result[k] = safe_i18n_get(i18n, key, **processed_sub_kwargs)

        # case {"key": "some.key", "value": 5}
        elif isinstance(v, dict) and "key" in v:
            key = v["key"]
            sub_kwargs = {sub_k: sub_v for sub_k, sub_v in v.items() if sub_k != "key"}
            processed_sub_kwargs = get_translated_kwargs(i18n, sub_kwargs)
            result[k] = safe_i18n_get(i18n, key, **processed_sub_kwargs)

        # case ["key", {"value": 5}]
        elif (
            isinstance(v, list) and len(v) == 2 and isinstance(v[0], str) and isinstance(v[1], dict)
        ):
            key, sub_kwargs = v
            processed_sub_kwargs = get_translated_kwargs(i18n, sub_kwargs)
            result[k] = safe_i18n_get(i18n, key, **processed_sub_kwargs)

        # case [("day", {"value": 6}), ("hour", {"value": 23})]
        elif isinstance(v, list) and all(
            isinstance(item, (tuple, list))
            and len(item) == 2
            and isinstance(item[0], str)
            and isinstance(item[1], dict)
            for item in v
        ):
            parts = [
                safe_i18n_get(i18n, item_key, **get_translated_kwargs(i18n, item_kwargs))
                for item_key, item_kwargs in v
            ]
            result[k] = " ".join(parts)

        # generic list
        elif isinstance(v, list):
            result[k] = [
                get_translated_kwargs(i18n, {"_": item})["_"]
                if isinstance(item, (tuple, dict, list))
                else item
                for item in v
            ]

        # fallback
        else:
            result[k] = v

    return result
