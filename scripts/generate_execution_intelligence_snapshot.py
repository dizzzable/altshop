#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "web-app" / "src" / "data" / "execution-intelligence-snapshot.json"
WINDOWS_PREFIX = str(REPO_ROOT).replace("\\", "/").rstrip("/")
LOW_SIGNAL_FILES = {"uv.lock", "web-app/package-lock.json"}
LOW_SIGNAL_SUFFIXES = (".lock",)
DOC_PREFIXES = ("docs/",)
TEST_PREFIXES = ("tests/",)
FRONTEND_PREFIXES = ("web-app/",)
HUNK_HEADER_RE = re.compile(
    r"^@@ -(?P<old_start>\d+)(?:,(?P<old_count>\d+))? \+(?P<new_start>\d+)(?:,(?P<new_count>\d+))? @@"
)
MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
BACKTICK_PATH_RE = re.compile(r"`((?:[A-Za-z]:/)?(?:[\w.-]+/)+[\w.-]+)`")
PLAIN_PATH_RE = re.compile(
    r"(?P<path>"
    r"(?:src|tests|docs|web-app|nginx|scripts|assets|\.github)/(?:[\w.-]+/)*[\w.-]+"
    r"|README\.md"
    r"|pyproject\.toml"
    r"|uv\.lock"
    r"|\.env\.example"
    r"|docker-compose(?:\.prod)?\.yml"
    r"|nginx/nginx\.conf"
    r"|web-app/package(?:-lock)?\.json"
    r")"
)
COMMAND_RE = re.compile(r"`((?:uv|npm|git|make|\$env:)[^`]+)`")
ISSUE_LINK_RE = re.compile(r"\[([A-Z]+-\d+)\]\(/([A-Z]+)/issues/([A-Z]+-\d+)\)")


CLUSTER_RULES: list[dict[str, Any]] = [
    {
        "id": "boundary-hardening",
        "title": "Boundary hardening and host enforcement",
        "issue_ids": ["ALT-32"],
        "patterns": [
            ".env.example",
            "src/api/app.py",
            "src/api/endpoints/health.py",
            "src/api/endpoints/internal.py",
            "src/core/config/app.py",
            "nginx/nginx.conf",
            "docker-compose.yml",
            "docker-compose.prod.yml",
            "README.md",
            "docs/08-configuration.md",
            "docs/09-deployment.md",
            "docs/10-development.md",
            "tests/services/test_fastapi_boundary.py",
            "tests/services/test_internal_readiness.py",
        ],
        "note": (
            "Trusted-host enforcement, a public liveness endpoint, and private-only "
            "readiness/metrics routing were wired through FastAPI, Nginx, compose, "
            "and the deployment docs."
        ),
        "note_type": "authored",
    },
    {
        "id": "payment-webhook-hardening",
        "title": "Payment webhook hardening",
        "issue_ids": ["ALT-31"],
        "patterns": [
            "src/api/endpoints/payments.py",
            "src/infrastructure/payment_gateways/cryptopay.py",
            "src/infrastructure/payment_gateways/mulenpay.py",
            "src/services/payment_gateway.py",
            "src/services/payment_webhook_event.py",
            "src/services/user_activity_portal.py",
            "tests/services/test_payment_gateway_use_cases.py",
            "tests/services/test_payment_gateway_webhook_security.py",
            "tests/services/test_payment_webhook_event.py",
            "tests/services/test_payments_webhook_endpoint.py",
            "docs/remnawave-compatibility.md",
        ],
        "note": (
            "Crypto Pay signature verification, MulenPay secret-path callbacks, and "
            "masked payment identifiers were added so public payment completion "
            "cannot be forged from unsigned payloads."
        ),
        "note_type": "authored",
    },
    {
        "id": "web-auth-split",
        "title": "Web auth orchestration split",
        "issue_ids": ["ALT-15"],
        "patterns": [
            "src/api/endpoints/web_auth.py",
            "src/api/utils/web_auth_transport.py",
            "src/api/utils/web_auth_rate_limit.py",
            "src/api/services/",
            "src/services/web_access_guard.py",
            "tests/services/test_web_auth_endpoint_contract.py",
            "tests/services/test_web_auth_rate_limits.py",
        ],
        "note": (
            "Large deletions in `src/api/endpoints/web_auth.py` are paired with new "
            "`src/api/services/` and `src/api/utils/web_auth_*` files, which points "
            "to endpoint thinning and extracted auth orchestration."
        ),
        "note_type": "inferred",
    },
    {
        "id": "dependency-gates",
        "title": "Dependency and CI security gates",
        "issue_ids": ["ALT-14", "ALT-34"],
        "patterns": [
            ".github/workflows/ci.yml",
            ".github/workflows/release.yml",
            "pyproject.toml",
            "uv.lock",
            "web-app/package.json",
            "web-app/package-lock.json",
            "docs/dependency-security-exceptions.md",
        ],
        "note": (
            "Backend checks, dependency audits, and secret scanning were added to CI "
            "and release workflows while vulnerable dependency floors and frontend "
            "overrides were updated."
        ),
        "note_type": "authored",
    },
    {
        "id": "web-app-refresh-ux",
        "title": "Web app refresh and accessibility pass",
        "issue_ids": ["ALT-4"],
        "patterns": [
            "web-app/src/components/layout/Header.tsx",
            "web-app/src/components/layout/MobileBottomBar.tsx",
            "web-app/src/components/layout/NotificationCenterDialog.tsx",
            "web-app/src/hooks/useAdaptivePollingInterval.ts",
            "web-app/src/hooks/useSubscriptionsQuery.ts",
            "web-app/src/lib/api.ts",
            "web-app/src/pages/auth/LoginPage.tsx",
            "web-app/src/pages/auth/RegisterPage.tsx",
            "web-app/src/i18n/locales/en.ts",
            "web-app/src/i18n/locales/ru.ts",
        ],
        "note": (
            "Visible-tab polling was replaced with adaptive backoff, duplicate "
            "`/user/me` reads were serialized, and the mobile/auth flows gained "
            "accessibility fixes."
        ),
        "note_type": "authored",
    },
]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def isoformat(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def read_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def normalize_collection(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [item for item in payload if isinstance(item, dict)]
    if isinstance(payload, dict):
        value = payload.get("value")
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        if "id" in payload:
            return [payload]
    return []


def paperclip_get(api_url: str, api_key: str, path: str) -> Any:
    request = Request(
        f"{api_url}{path}",
        headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
    )
    try:
        with urlopen(request) as response:
            return json.load(response)
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Paperclip GET {path} failed with {exc.code}: {body}") from exc
    except URLError as exc:
        raise RuntimeError(f"Paperclip GET {path} failed: {exc.reason}") from exc


def run_git(*args: str) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout


def repo_relative(value: str) -> str:
    normalized = value.replace("\\", "/").strip()
    if normalized.startswith(WINDOWS_PREFIX):
        return normalized[len(WINDOWS_PREFIX) + 1 :]
    return normalized.lstrip("./")


def unique_strings(values: list[str]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        output.append(value)
    return output


def should_ignore_path(path: str) -> bool:
    return path.startswith(".agents/") or path == "web-app/src/data/execution-intelligence-snapshot.json"


def extract_paths(text: str | None) -> list[str]:
    if not text:
        return []

    paths: list[str] = []
    for _, target in MARKDOWN_LINK_RE.findall(text):
        if target.startswith("http://") or target.startswith("https://") or target.startswith("/"):
            continue
        relative = repo_relative(target)
        if (REPO_ROOT / relative).exists():
            paths.append(relative)

    for match in BACKTICK_PATH_RE.findall(text):
        relative = repo_relative(match)
        if (REPO_ROOT / relative).exists():
            paths.append(relative)

    for match in PLAIN_PATH_RE.finditer(text):
        relative = repo_relative(match.group("path"))
        if (REPO_ROOT / relative).exists():
            paths.append(relative)

    return unique_strings(paths)


def extract_commands(text: str | None) -> list[str]:
    if not text:
        return []
    return unique_strings([command.strip() for command in COMMAND_RE.findall(text)])


def summarize_markdown(text: str | None, limit: int = 260) -> str | None:
    if not text:
        return None

    normalized = MARKDOWN_LINK_RE.sub(lambda match: match.group(1), text)
    normalized = normalized.replace("`", "")
    normalized = re.sub(r"^#+\s*", "", normalized, flags=re.MULTILINE)
    normalized = re.sub(r"^\s*[-*]\s*", "", normalized, flags=re.MULTILINE)
    normalized = re.sub(r"\s+", " ", normalized).strip()
    if not normalized:
        return None
    if len(normalized) <= limit:
        return normalized
    return normalized[: limit - 1].rstrip() + "…"


def parse_git_status() -> dict[str, dict[str, Any]]:
    output = run_git("status", "--porcelain=v1", "--untracked-files=all")
    changes: dict[str, dict[str, Any]] = {}

    for raw_line in output.splitlines():
        if len(raw_line) < 4:
            continue

        code = raw_line[:2]
        raw_path = raw_line[3:]
        path = raw_path.split(" -> ", 1)[-1]
        if should_ignore_path(path):
            continue

        if code == "??":
            status = "untracked"
        elif "R" in code:
            status = "renamed"
        elif "D" in code:
            status = "deleted"
        elif "A" in code:
            status = "added"
        else:
            status = "modified"

        changes[path] = {
            "path": path,
            "status": status,
            "insertions": 0,
            "deletions": 0,
            "ranges": [],
        }

    return changes


def parse_git_numstat(changes: dict[str, dict[str, Any]]) -> None:
    output = run_git("diff", "--numstat", "--")
    for line in output.splitlines():
        if not line.strip():
            continue
        additions_raw, deletions_raw, path = line.split("\t", 2)
        if should_ignore_path(path):
            continue
        entry = changes.setdefault(
            path,
            {"path": path, "status": "modified", "insertions": 0, "deletions": 0, "ranges": []},
        )
        entry["insertions"] = 0 if additions_raw == "-" else int(additions_raw)
        entry["deletions"] = 0 if deletions_raw == "-" else int(deletions_raw)


def parse_git_hunks(changes: dict[str, dict[str, Any]]) -> None:
    output = run_git("diff", "--unified=0", "--no-color", "--")
    current_path: str | None = None

    for line in output.splitlines():
        if line.startswith("diff --git "):
            parts = line.split(" ")
            if len(parts) >= 4:
                current_path = parts[3][2:]
                if should_ignore_path(current_path):
                    current_path = None
            continue

        if current_path is None or not line.startswith("@@ "):
            continue

        match = HUNK_HEADER_RE.match(line)
        if not match:
            continue

        old_start = int(match.group("old_start"))
        old_count = int(match.group("old_count") or "1")
        new_start = int(match.group("new_start"))
        new_count = int(match.group("new_count") or "1")

        if old_count == 0:
            kind = "new"
            start = new_start
            end = new_start + new_count - 1
            display = f"{start}-{end}" if start != end else str(start)
        elif new_count == 0:
            kind = "deleted"
            start = old_start
            end = old_start + old_count - 1
            display = f"old {start}-{end}" if start != end else f"old {start}"
        else:
            kind = "edited"
            start = new_start
            end = new_start + new_count - 1
            display = f"{start}-{end}" if start != end else str(start)

        entry = changes.setdefault(
            current_path,
            {"path": current_path, "status": "modified", "insertions": 0, "deletions": 0, "ranges": []},
        )
        entry["ranges"].append(
            {
                "kind": kind,
                "start": start,
                "end": end,
                "display": display,
            }
        )


def count_file_lines(path: Path) -> int:
    try:
        with path.open("r", encoding="utf-8") as handle:
            return sum(1 for _ in handle)
    except UnicodeDecodeError:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            return sum(1 for _ in handle)


def finalize_changed_files() -> tuple[list[dict[str, Any]], dict[str, int]]:
    changes = parse_git_status()
    parse_git_numstat(changes)
    parse_git_hunks(changes)

    totals = {"changedFiles": 0, "insertions": 0, "deletions": 0}
    entries: list[dict[str, Any]] = []

    for path, entry in changes.items():
        repo_path = REPO_ROOT / path
        if repo_path.is_dir():
            continue
        if entry["status"] == "untracked":
            line_count = count_file_lines(repo_path) if repo_path.exists() else 0
            entry["insertions"] = line_count
            if not entry["ranges"] and line_count:
                entry["ranges"].append(
                    {
                        "kind": "new",
                        "start": 1,
                        "end": line_count,
                        "display": f"1-{line_count}" if line_count > 1 else "1",
                    }
                )

        area = path.split("/", 1)[0] if "/" in path else "root"
        magnitude = entry["insertions"] + entry["deletions"]
        penalty = 1.0
        if path in LOW_SIGNAL_FILES or path.endswith(LOW_SIGNAL_SUFFIXES):
            penalty = 0.1
        elif path.startswith(DOC_PREFIXES):
            penalty = 0.7
        elif path.startswith(TEST_PREFIXES):
            penalty = 0.85
        elif path.startswith(FRONTEND_PREFIXES):
            penalty = 0.95

        signal_score = round((magnitude or max(len(entry["ranges"]) * 10, 1)) * penalty, 2)
        entries.append(
            {
                "path": path,
                "status": entry["status"],
                "area": area,
                "insertions": entry["insertions"],
                "deletions": entry["deletions"],
                "ranges": entry["ranges"],
                "signalScore": signal_score,
                "lowSignal": penalty < 0.2,
            }
        )
        totals["changedFiles"] += 1
        totals["insertions"] += entry["insertions"]
        totals["deletions"] += entry["deletions"]

    entries.sort(key=lambda item: (item["signalScore"], item["insertions"] + item["deletions"]), reverse=True)
    return entries, totals


def parse_recent_commits(limit: int = 12) -> list[dict[str, str]]:
    output = run_git(
        "log",
        f"-n{limit}",
        "--date=iso",
        "--pretty=format:%H%x09%ad%x09%an%x09%s",
    )
    commits: list[dict[str, str]] = []
    for line in output.splitlines():
        full_hash, authored_at, author, subject = line.split("\t", 3)
        commits.append(
            {
                "hash": full_hash,
                "shortHash": full_hash[:7],
                "authoredAt": authored_at,
                "author": author,
                "subject": subject,
            }
        )
    return commits


def build_issue_record(
    issue: dict[str, Any],
    prefix: str,
    parent_lookup: dict[str, str],
    agents_by_id: dict[str, dict[str, Any]],
    latest_comments: dict[str, dict[str, Any] | None],
) -> dict[str, Any]:
    latest_comment = latest_comments.get(issue["id"])
    comment_body = latest_comment.get("body") if latest_comment else None
    description_paths = extract_paths(issue.get("description"))
    comment_paths = extract_paths(comment_body)
    evidence_paths = unique_strings(description_paths + comment_paths)

    assignee_agent = agents_by_id.get(issue.get("assigneeAgentId") or "")
    assignee_name = "Board" if issue.get("assigneeUserId") else None
    assignee_url = None
    if assignee_agent:
        assignee_name = assignee_agent["name"]
        assignee_url = f"/{prefix}/agents/{assignee_agent['urlKey']}"

    active_run = issue.get("activeRun") or {}

    return {
        "id": issue["id"],
        "identifier": issue["identifier"],
        "title": issue["title"],
        "status": issue["status"],
        "priority": issue["priority"],
        "link": f"/{prefix}/issues/{issue['identifier']}",
        "parentIdentifier": parent_lookup.get(issue.get("parentId") or ""),
        "parentLink": (
            f"/{prefix}/issues/{parent_lookup[issue['parentId']]}"
            if issue.get("parentId") in parent_lookup
            else None
        ),
        "assigneeName": assignee_name,
        "assigneeUrl": assignee_url,
        "updatedAt": issue.get("updatedAt"),
        "createdAt": issue.get("createdAt"),
        "startedAt": issue.get("startedAt"),
        "completedAt": issue.get("completedAt"),
        "descriptionExcerpt": summarize_markdown(issue.get("description")),
        "evidencePaths": evidence_paths[:12],
        "commands": extract_commands(comment_body)[:8],
        "latestComment": {
            "id": latest_comment.get("id") if latest_comment else None,
            "excerpt": summarize_markdown(comment_body),
            "paths": comment_paths[:12],
            "createdAt": latest_comment.get("createdAt") if latest_comment else None,
            "hasStructuredEvidence": bool(comment_paths or extract_commands(comment_body)),
        },
        "activeRunId": active_run.get("id"),
    }


def sort_by_datetime(items: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    return sorted(
        items,
        key=lambda item: parse_datetime(item.get(key)) or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )


def build_agent_lanes(
    prefix: str,
    agents: list[dict[str, Any]],
    issue_records: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    records_by_assignee: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for issue in issue_records:
        if issue.get("assigneeName"):
            records_by_assignee[issue["assigneeName"]].append(issue)

    recent_threshold = utc_now() - timedelta(hours=24)
    lanes: list[dict[str, Any]] = []

    for agent in agents:
        assigned = records_by_assignee.get(agent["name"], [])
        open_issues = [issue for issue in assigned if issue["status"] in {"todo", "in_progress", "blocked", "in_review"}]
        recent_done = [
            issue
            for issue in assigned
            if issue["status"] == "done"
            and (parse_datetime(issue.get("completedAt")) or datetime.min.replace(tzinfo=timezone.utc)) >= recent_threshold
        ]
        if not open_issues and not recent_done:
            continue

        evidence_paths = unique_strings(
            [path for issue in open_issues + recent_done for path in issue.get("evidencePaths", [])]
        )[:10]
        lanes.append(
            {
                "id": agent["id"],
                "name": agent["name"],
                "title": agent.get("title"),
                "status": agent.get("status"),
                "role": agent.get("role"),
                "capabilities": summarize_markdown(agent.get("capabilities"), limit=220),
                "link": f"/{prefix}/agents/{agent['urlKey']}",
                "openIssues": sort_by_datetime(open_issues, "updatedAt")[:4],
                "recentDoneIssues": sort_by_datetime(recent_done, "completedAt")[:4],
                "completedLast24h": len(recent_done),
                "evidencePaths": evidence_paths,
            }
        )

    lanes.sort(
        key=lambda lane: (
            len(lane["openIssues"]),
            lane["completedLast24h"],
            1 if lane["status"] == "running" else 0,
        ),
        reverse=True,
    )
    return lanes


def build_parent_tracks(
    prefix: str,
    issues: list[dict[str, Any]],
    issue_records_by_id: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    children_by_parent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    issues_by_id = {issue["id"]: issue for issue in issues}
    for issue in issues:
        parent_id = issue.get("parentId")
        if parent_id:
            children_by_parent[parent_id].append(issue)

    tracks: list[dict[str, Any]] = []
    for parent_id, children in children_by_parent.items():
        parent = issues_by_id.get(parent_id)
        if not parent:
            continue
        child_records = [issue_records_by_id[child["id"]] for child in children if child["id"] in issue_records_by_id]
        if not child_records:
            continue
        status_counts = Counter(record["status"] for record in child_records)
        latest_updated = max(
            parse_datetime(record["updatedAt"]) or datetime.min.replace(tzinfo=timezone.utc)
            for record in child_records
        )
        tracks.append(
            {
                "identifier": parent["identifier"],
                "title": parent["title"],
                "link": f"/{prefix}/issues/{parent['identifier']}",
                "status": parent["status"],
                "counts": dict(status_counts),
                "latestUpdatedAt": isoformat(latest_updated),
                "children": sort_by_datetime(child_records, "updatedAt")[:6],
            }
        )

    tracks.sort(
        key=lambda track: (
            track["counts"].get("in_progress", 0) + track["counts"].get("todo", 0) + track["counts"].get("blocked", 0),
            parse_datetime(track["latestUpdatedAt"]) or datetime.min.replace(tzinfo=timezone.utc),
        ),
        reverse=True,
    )
    return tracks


def build_change_clusters(
    issue_records_by_identifier: dict[str, dict[str, Any]],
    changed_files: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    changed_paths = {file["path"] for file in changed_files}
    clusters: list[dict[str, Any]] = []

    for rule in CLUSTER_RULES:
        matched_paths = [
            path
            for path in changed_paths
            if any(path == pattern or path.startswith(pattern) for pattern in rule["patterns"])
        ]
        if not matched_paths:
            continue

        issues = [
            issue_records_by_identifier[issue_id]
            for issue_id in rule["issue_ids"]
            if issue_id in issue_records_by_identifier
        ]
        authored_comment = next(
            (
                issue["latestComment"]["excerpt"]
                for issue in issues
                if issue["latestComment"]["excerpt"] and issue["latestComment"]["hasStructuredEvidence"]
            ),
            None,
        )
        clusters.append(
            {
                "id": rule["id"],
                "title": rule["title"],
                "note": authored_comment or rule["note"],
                "noteType": "authored" if authored_comment else rule["note_type"],
                "issues": [
                    {
                        "identifier": issue["identifier"],
                        "title": issue["title"],
                        "status": issue["status"],
                        "link": issue["link"],
                    }
                    for issue in issues
                ],
                "files": sorted(matched_paths)[:14],
            }
        )

    return clusters


def build_capability_gaps(prefix: str) -> list[dict[str, Any]]:
    return [
        {
            "kind": "skill",
            "title": "Company-owned AltShop Remnawave and payment integrations skill",
            "owner": "Backend Architect / Skills Engineer",
            "status": "todo",
            "link": f"/{prefix}/issues/ALT-29",
            "evidence": "ALT-29 is the only remaining project todo and packages Remnawave plus gateway knowledge for other lanes.",
        },
        {
            "kind": "playbook",
            "title": "Frontend browser verification harness for slow, offline, and locale-specific states",
            "owner": "Founding Engineer",
            "status": "follow-up",
            "link": f"/{prefix}/issues/ALT-4",
            "evidence": "ALT-4 closed with a residual note that the web app still lacks dedicated frontend verification for those states.",
        },
        {
            "kind": "operations",
            "title": "MulenPay production webhook_secret rollout note",
            "owner": "PaymentsMaster / Founding Engineer",
            "status": "follow-up",
            "link": f"/{prefix}/issues/ALT-31",
            "evidence": "ALT-31 now requires an app-owned `webhook_secret` before MulenPay webhooks can be safely accepted in production.",
        },
    ]


def build_reporting_gaps() -> tuple[list[str], list[dict[str, str]]]:
    gaps = [
        "Paperclip issues do not have first-class commit linkage, so issue-to-file attribution still depends on authored comments and git proximity.",
        "Completion-comment quality is inconsistent: ALT-31, ALT-32, ALT-34, ALT-14, and ALT-4 contain structured evidence, while ALT-15 currently does not.",
        "The current working tree is still dirty, which exposes line-range evidence for live rework but not merged commit boundaries for each task.",
    ]
    follow_up_tasks = [
        {
            "title": "Add issue-to-commit provenance capture to the execution pipeline",
            "owner": "Chief of Staff",
            "evidence": "The dashboard can show commit history and issue history, but it still has to correlate them manually.",
        },
        {
            "title": "Standardize completion comments with changed paths, commands, and test evidence",
            "owner": "Chief of Staff",
            "evidence": "ALT-15 currently lacks the structured handoff shape already used in ALT-31, ALT-32, ALT-34, and ALT-14.",
        },
        {
            "title": "Finish and sync the AltShop integrations skill rollout",
            "owner": "Backend Architect / Skills Engineer",
            "evidence": "ALT-29 is still open, and it directly reduces future reporting ambiguity around Remnawave and payment-lane work.",
        },
    ]
    return gaps, follow_up_tasks


def main() -> int:
    output_path = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else DEFAULT_OUTPUT

    api_url = read_env("PAPERCLIP_API_URL")
    api_key = read_env("PAPERCLIP_API_KEY")
    company_id = read_env("PAPERCLIP_COMPANY_ID")
    task_id = read_env("PAPERCLIP_TASK_ID")

    heartbeat_context = paperclip_get(api_url, api_key, f"/api/issues/{task_id}/heartbeat-context")
    current_issue = heartbeat_context["issue"]
    project = heartbeat_context["project"]
    goal = heartbeat_context["goal"]
    prefix = current_issue["identifier"].split("-", 1)[0]

    company_dashboard = paperclip_get(api_url, api_key, f"/api/companies/{company_id}/dashboard")
    agents = normalize_collection(paperclip_get(api_url, api_key, f"/api/companies/{company_id}/agents"))
    issues = normalize_collection(
        paperclip_get(api_url, api_key, f"/api/companies/{company_id}/issues?projectId={project['id']}")
    )

    agents_by_id = {agent["id"]: agent for agent in agents}
    parent_lookup = {issue["id"]: issue["identifier"] for issue in issues}

    latest_comments: dict[str, dict[str, Any] | None] = {}
    for issue in issues:
        comments_payload = paperclip_get(api_url, api_key, f"/api/issues/{issue['id']}/comments")
        comments = normalize_collection(comments_payload)
        comments.sort(
            key=lambda item: parse_datetime(item.get("createdAt")) or datetime.min.replace(tzinfo=timezone.utc)
        )
        latest_comments[issue["id"]] = comments[-1] if comments else None

    issue_records = [
        build_issue_record(issue, prefix, parent_lookup, agents_by_id, latest_comments)
        for issue in issues
    ]
    issue_records_by_id = {issue["id"]: issue for issue in issue_records}
    issue_records_by_identifier = {issue["identifier"]: issue for issue in issue_records}

    status_counts = Counter(issue["status"] for issue in issues)
    now = utc_now()
    done_last_24h = [
        issue
        for issue in issue_records
        if issue["status"] == "done"
        and (parse_datetime(issue["completedAt"]) or datetime.min.replace(tzinfo=timezone.utc)) >= now - timedelta(hours=24)
    ]

    changed_files, diff_totals = finalize_changed_files()
    recent_commits = parse_recent_commits(limit=12)
    change_clusters = build_change_clusters(issue_records_by_identifier, changed_files)
    parent_tracks = build_parent_tracks(prefix, issues, issue_records_by_id)
    agent_lanes = build_agent_lanes(prefix, agents, issue_records)
    capability_gaps = build_capability_gaps(prefix)
    reporting_gaps, follow_up_tasks = build_reporting_gaps()

    open_statuses = {"todo", "in_progress", "blocked", "in_review"}
    open_issue_identifiers = [
        issue["identifier"]
        for issue in sort_by_datetime([issue for issue in issue_records if issue["status"] in open_statuses], "updatedAt")
    ]

    snapshot = {
        "generatedAt": isoformat(now),
        "context": {
            "companyPrefix": prefix,
            "issue": {
                "identifier": current_issue["identifier"],
                "title": current_issue["title"],
                "link": f"/{prefix}/issues/{current_issue['identifier']}",
            },
            "project": {
                "id": project["id"],
                "name": project["name"],
                "status": project["status"],
            },
            "goal": {
                "id": goal["id"],
                "title": goal["title"],
                "status": goal["status"],
            },
            "git": {
                "branch": run_git("rev-parse", "--abbrev-ref", "HEAD").strip(),
                "head": run_git("rev-parse", "HEAD").strip(),
                "headShort": run_git("rev-parse", "--short", "HEAD").strip(),
            },
        },
        "summary": {
            "projectIssuesTotal": len(issue_records),
            "projectStatusCounts": {
                "done": status_counts.get("done", 0),
                "inProgress": status_counts.get("in_progress", 0),
                "todo": status_counts.get("todo", 0),
                "blocked": status_counts.get("blocked", 0),
                "inReview": status_counts.get("in_review", 0),
            },
            "companyDashboard": company_dashboard,
            "recentCompleted24h": len(done_last_24h),
            "openIssueIdentifiers": open_issue_identifiers,
            "changedFiles": diff_totals["changedFiles"],
            "insertions": diff_totals["insertions"],
            "deletions": diff_totals["deletions"],
            "agentsTotal": len(agents),
            "agentsRunning": sum(1 for agent in agents if agent.get("status") == "running"),
        },
        "statusLanes": {
            "inProgress": sort_by_datetime([issue for issue in issue_records if issue["status"] == "in_progress"], "updatedAt"),
            "todo": sort_by_datetime([issue for issue in issue_records if issue["status"] == "todo"], "updatedAt"),
            "blocked": sort_by_datetime([issue for issue in issue_records if issue["status"] == "blocked"], "updatedAt"),
            "inReview": sort_by_datetime([issue for issue in issue_records if issue["status"] == "in_review"], "updatedAt"),
            "done": sort_by_datetime([issue for issue in issue_records if issue["status"] == "done"], "completedAt"),
        },
        "recentDoneIssues": sort_by_datetime([issue for issue in issue_records if issue["status"] == "done"], "completedAt")[:8],
        "parentTracks": parent_tracks[:8],
        "agentLanes": agent_lanes[:8],
        "changeClusters": change_clusters,
        "changedFiles": changed_files,
        "recentCommits": recent_commits,
        "capabilityGaps": capability_gaps,
        "reportingGaps": reporting_gaps,
        "followUpTasks": follow_up_tasks,
        "inspectedIssueIdentifiers": [
            "ALT-44",
            "ALT-29",
            "ALT-15",
            "ALT-31",
            "ALT-32",
            "ALT-34",
            "ALT-14",
            "ALT-4",
            "ALT-1",
        ],
        "inspectedRepoPaths": [
            ".github/workflows/ci.yml",
            ".github/workflows/release.yml",
            ".env.example",
            "README.md",
            "docs/dependency-security-exceptions.md",
            "docs/remnawave-compatibility.md",
            "nginx/nginx.conf",
            "src/api/app.py",
            "src/api/endpoints/internal.py",
            "src/api/endpoints/payments.py",
            "src/api/endpoints/web_auth.py",
            "src/api/services/",
            "src/api/utils/web_auth_transport.py",
            "src/infrastructure/payment_gateways/cryptopay.py",
            "src/infrastructure/payment_gateways/mulenpay.py",
            "src/services/payment_gateway.py",
            "src/services/remnawave.py",
            "src/services/subscription_purchase.py",
            "src/services/user_activity_portal.py",
            "tests/services/test_fastapi_boundary.py",
            "tests/services/test_payment_gateway_webhook_security.py",
            "tests/services/test_user_activity_portal.py",
            "tests/services/test_web_auth_endpoint_contract.py",
            "tests/services/test_web_auth_rate_limits.py",
            "web-app/src/components/layout/Header.tsx",
            "web-app/src/components/layout/MobileBottomBar.tsx",
            "web-app/src/components/layout/NotificationCenterDialog.tsx",
            "web-app/src/hooks/useAdaptivePollingInterval.ts",
            "web-app/src/hooks/useSubscriptionsQuery.ts",
            "web-app/src/lib/api.ts",
        ],
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(snapshot, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote execution-intelligence snapshot to {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
