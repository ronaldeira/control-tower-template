#!/usr/bin/env python3
"""Control Tower — dependency-free dashboard generator (Python 3.11+, stdlib only)."""
from __future__ import annotations

import re
import tomllib
from datetime import datetime, timezone

PROJECT_ID_RE = re.compile(r'^[a-z0-9_-]+$')
REPO_RE = re.compile(r'^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$')


class ConfigError(Exception):
    """Raised when the config file is malformed or violates a rule."""


def mode_of(project: dict) -> str:
    """A project is local mode iff it declares a `path` key, else remote mode."""
    return "local" if "path" in project else "remote"


def validate_config(cfg: dict, *, strict_remote_only: bool = False) -> None:
    projects = cfg.get("projects", [])
    if not isinstance(projects, list):
        raise ConfigError("`projects` must be an array of tables")
    for i, p in enumerate(projects):
        where = f"project #{i + 1}"
        pid = p.get("id", "")
        if not PROJECT_ID_RE.match(str(pid)):
            raise ConfigError(f"{where}: id {pid!r} must match ^[a-z0-9_-]+$")
        if "repo" in p and not REPO_RE.match(str(p["repo"])):
            raise ConfigError(f"{where}: repo {p['repo']!r} must be 'owner/name'")
        if mode_of(p) == "remote" and "repo" not in p:
            raise ConfigError(f"{where}: remote entry requires a `repo`")
        if strict_remote_only:
            for forbidden in ("path", "services"):
                if forbidden in p:
                    raise ConfigError(
                        f"{where}: shipped/CI config must be remote-only; "
                        f"remove `{forbidden}`"
                    )


def load_config(path: str, *, strict_remote_only: bool = False) -> dict:
    with open(path, "rb") as fh:
        cfg = tomllib.load(fh)
    cfg.setdefault("dashboard", {})
    cfg.setdefault("projects", [])
    validate_config(cfg, strict_remote_only=strict_remote_only)
    return cfg


def parse_ts(value):
    """Parse an ISO-8601 timestamp (with optional trailing Z) to aware UTC."""
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def relative_age(then, now):
    """Human 'time ago' label; '' when unknown."""
    if then is None:
        return ""
    delta = now - then
    hours = delta.total_seconds() / 3600
    if hours < 1:
        return "just now"
    if hours < 24:
        return f"{int(hours)}h ago"
    return f"{int(hours // 24)}d ago"


def is_fresh(last_activity, now, fresh_hours):
    """True when activity falls within the freshness window."""
    if last_activity is None:
        return False
    return (now - last_activity).total_seconds() <= fresh_hours * 3600
