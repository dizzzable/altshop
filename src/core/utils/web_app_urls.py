from urllib.parse import urlparse, urlunparse


def _build_url(raw_url: str, target_path: str) -> str:
    parsed = urlparse(raw_url.strip())
    return urlunparse(
        parsed._replace(
            path=target_path,
            params="",
            query="",
            fragment="",
        )
    )


def to_webapp_base_url(raw_url: str) -> str:
    path = urlparse(raw_url.strip()).path.rstrip("/")

    if path.endswith("/webapp/miniapp"):
        target_path = path[: -len("/miniapp")]
    elif path.endswith("/webapp"):
        target_path = path
    elif path.endswith("/miniapp"):
        target_path = path[: -len("/miniapp")]
    elif not path:
        target_path = "/webapp"
    else:
        target_path = f"{path}/webapp"

    return _build_url(raw_url, target_path)
