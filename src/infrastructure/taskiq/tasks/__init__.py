"""Taskiq task package.

Keep this package lazy: importing one task module should not eagerly import the whole task graph.
That avoids accidental import cycles between services and unrelated task modules.
"""

__all__ = [
    "broadcast",
    "importer",
    "notifications",
    "payments",
    "redirects",
    "referrals",
    "subscriptions",
    "updates",
]
