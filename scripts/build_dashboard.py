#!/usr/bin/env python3
"""Control Tower — dependency-free dashboard generator (Python 3.11+, stdlib only)."""
from __future__ import annotations

import re
import tomllib

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
