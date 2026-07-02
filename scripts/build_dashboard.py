#!/usr/bin/env python3
"""Control Tower — dependency-free dashboard generator (Python 3.11+, stdlib only)."""
from __future__ import annotations

import argparse
import html
import os
import re
import subprocess
import sys
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


def esc(x):
    return html.escape(str(x))


def build_row(project, live, now, fresh_hours):
    la = live.get("last_activity")
    return {
        "id": project["id"],
        "name": project["name"],
        "mode": mode_of(project),
        "repo": project.get("repo", ""),
        "url": project.get("url", ""),
        "branch": live.get("branch") or "(detached)",
        "version": live.get("version") or "(no tags)",
        "prs": live.get("prs", "n/a") if live.get("prs") is not None else "n/a",
        "issues": live.get("issues", "n/a") if live.get("issues") is not None else "n/a",
        "stars": live.get("stars", "n/a") if live.get("stars") is not None else "n/a",
        "ci": live.get("ci") or "n/a",
        "up": live.get("up"),
        "age_label": relative_age(la, now),
        "is_new": is_fresh(la, now, fresh_hours),
    }


def _up_badge(up):
    if up is True:
        return '<span class="up ok">● up</span>'
    if up is False:
        return '<span class="up down">● down</span>'
    return ""


def _card(row):
    new = '<span class="new">● NEW</span>' if row["is_new"] else ""
    age = f'<span class="age">{esc(row["age_label"])}</span>' if row["age_label"] else ""
    repo = esc(row["repo"])
    repo_link = (f'<a href="https://github.com/{repo}" target="_blank" '
                 f'rel="noopener">{repo}</a>') if row["repo"] else ""
    url = esc(row["url"])
    url_link = (f'<a href="{url}" target="_blank" rel="noopener">{_up_badge(row["up"])}</a>'
                if row["url"] else _up_badge(row["up"]))
    return f"""
    <div class="card">
      <div class="card-head"><h2>{esc(row["name"])}</h2>{new}{age}</div>
      <div class="meta">{repo_link}</div>
      <ul class="stats">
        <li>branch: <code>{esc(row["branch"])}</code></li>
        <li>version: <code>{esc(row["version"])}</code></li>
        <li>PRs: {esc(row["prs"])} · issues: {esc(row["issues"])}</li>
        <li>★ {esc(row["stars"])} · CI: {esc(row["ci"])}</li>
        <li>{url_link}</li>
      </ul>
    </div>"""


_STYLE = """
  body{font-family:system-ui,sans-serif;background:#0d1117;color:#e6edf3;margin:0;padding:24px}
  h1{font-size:20px}
  .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(260px,1fr));gap:16px}
  .card{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:14px}
  .card-head{display:flex;align-items:center;gap:8px}
  .card-head h2{font-size:15px;margin:0;flex:1}
  .new{color:#3fb950;font-weight:600;font-size:12px}
  .age{color:#8b949e;font-size:12px}
  .stats{list-style:none;padding:0;margin:8px 0 0;font-size:13px;color:#c9d1d9}
  .stats li{margin:3px 0}
  code{background:#0d1117;padding:1px 5px;border-radius:4px}
  .up.ok{color:#3fb950}.up.down{color:#f85149}
  .env{color:#8b949e;font-size:12px;margin-bottom:16px}
  a{color:#58a6ff;text-decoration:none}
"""


def render_html(rows, *, title, include_env=True, env=None):
    cards = "\n".join(_card(r) for r in rows)
    env_html = ""
    if include_env and env:
        env_html = (f'<div class="env">🖥️ {esc(env.get("host", ""))} · '
                    f'{esc(env.get("note", ""))}</div>')
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>{esc(title)}</title><style>{_STYLE}</style></head>
<body>
  <h1>{esc(title)}</h1>
  {env_html}
  <div class="grid">{cards}
  </div>
</body></html>"""


def demo_projects():
    return [
        {"id": "demo-api", "name": "Demo API", "repo": "acme/demo-api",
         "url": "https://example.com"},
        {"id": "demo-web", "name": "Demo Web", "repo": "acme/demo-web"},
        {"id": "demo-worker", "name": "Demo Worker", "repo": "acme/demo-worker"},
    ]


def demo_live(project, now):
    from datetime import timedelta
    seed = {"demo-api": 2, "demo-web": 30, "demo-worker": 100}.get(project["id"], 5)
    return {"branch": "main", "version": "v1.2.3", "prs": seed % 5,
            "issues": seed % 3, "stars": seed * 7, "ci": "success",
            "up": True, "last_activity": now - timedelta(hours=seed)}


def run_cmd(cmd, *, timeout, cwd=None):
    """List-form subprocess; returns stripped stdout, '' on any failure. Never shell=True."""
    try:
        res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                             timeout=timeout, check=False)
    except (OSError, subprocess.SubprocessError):
        return ""
    return res.stdout.strip()


def _http_up(url, timeout=8):
    import urllib.request
    req = urllib.request.Request(url, method="HEAD")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return 200 <= resp.status < 400
    except Exception:
        return False


def collect_local(project, *, now):
    path = project["path"]
    live = {"last_activity": None}
    if os.path.isdir(os.path.join(path, ".git")) or os.path.isdir(path):
        branch = run_cmd(["git", "branch", "--show-current"], timeout=15, cwd=path)
        if branch:
            live["branch"] = branch
        tag = run_cmd(["git", "describe", "--tags", "--abbrev=0"], timeout=15, cwd=path)
        if tag:
            live["version"] = tag
        last = run_cmd(["git", "log", "-1", "--format=%cI"], timeout=15, cwd=path)
        if last:
            live["last_activity"] = parse_ts(last)
    services = project.get("services", {})
    for name in services.get("pm2", []):
        out = run_cmd(["pm2", "jlist"], timeout=15)  # presence check; count if listed
        if out and name in out:
            live["ci"] = "pm2 up"
    urls = project.get("urls", {})
    if urls.get("prod"):
        live["up"] = _http_up(urls["prod"])
    return live


def collect_live(project, *, token=None, now=None):
    """Dispatch to local/remote collectors. Filled in Tasks 6-7."""
    return {}


def _build(cfg, *, demo, include_env, now, token):
    fresh = int(cfg.get("dashboard", {}).get("fresh_hours", 48))
    title = cfg.get("dashboard", {}).get("title", "Control Tower")
    projects = demo_projects() if demo else cfg.get("projects", [])
    rows = []
    for p in projects:
        live = demo_live(p, now) if demo else collect_live(p, token=token, now=now)
        rows.append(build_row(p, live, now, fresh))
    # env header suppressed when any project is remote mode
    any_remote = any(mode_of(p) == "remote" for p in projects)
    env = None if (demo or any_remote or not include_env) else {"host": "localhost", "note": ""}
    return render_html(rows, title=title, include_env=include_env and env is not None, env=env)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Control Tower dashboard generator")
    ap.add_argument("--config", default="control-tower.config.toml")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--no-env", action="store_true")
    ap.add_argument("-o", "--out", default="dashboard.html")
    args = ap.parse_args(argv)

    now = datetime.now(timezone.utc)
    if args.demo:
        cfg = {"dashboard": {"title": "Control Tower — Demo"}, "projects": demo_projects()}
    else:
        try:
            cfg = load_config(args.config)
        except (OSError, ConfigError) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
    if args.dry_run:
        print("ok: config valid")
        return 0
    import os
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    out_html = _build(cfg, demo=args.demo, include_env=not args.no_env, now=now, token=token)
    with open(args.out, "w", encoding="utf-8") as fh:
        fh.write(out_html)
    print(f"ok: wrote {args.out} ({len(cfg.get('projects', []))} projects)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
