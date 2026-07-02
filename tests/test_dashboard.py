# tests/test_dashboard.py
import textwrap
import pytest
import build_dashboard as bd
from datetime import datetime, timezone, timedelta
from pathlib import Path


def _write(tmp_path, toml_text):
    p = tmp_path / "cfg.toml"
    p.write_text(textwrap.dedent(toml_text))
    return str(p)


def test_mode_of_detects_local_and_remote():
    assert bd.mode_of({"id": "a", "path": "/x"}) == "local"
    assert bd.mode_of({"id": "a", "repo": "o/r"}) == "remote"


def test_mode_of_uses_key_presence_not_truthiness():
    # A path key present but empty is still local mode.
    assert bd.mode_of({"id": "a", "path": ""}) == "local"


def test_load_valid_remote_config(tmp_path):
    cfg = bd.load_config(_write(tmp_path, """
        [dashboard]
        title = "T"
        fresh_hours = 24
        [[projects]]
        id = "aquila-guardian"
        name = "Aquila"
        repo = "owner/aquila-guardian"
    """))
    assert cfg["dashboard"]["title"] == "T"
    assert cfg["projects"][0]["id"] == "aquila-guardian"


def test_invalid_id_rejected(tmp_path):
    with pytest.raises(bd.ConfigError, match="id"):
        bd.load_config(_write(tmp_path, """
            [[projects]]
            id = "Bad Id;rm"
            name = "X"
            repo = "o/r"
        """))


def test_bad_repo_rejected(tmp_path):
    with pytest.raises(bd.ConfigError, match="repo"):
        bd.load_config(_write(tmp_path, """
            [[projects]]
            id = "x"
            name = "X"
            repo = "not-a-repo"
        """))


def test_remote_entry_without_repo_rejected(tmp_path):
    with pytest.raises(bd.ConfigError, match="repo"):
        bd.load_config(_write(tmp_path, """
            [[projects]]
            id = "x"
            name = "X"
        """))


def test_strict_remote_only_rejects_path(tmp_path):
    with pytest.raises(bd.ConfigError, match="remote-only"):
        bd.load_config(_write(tmp_path, """
            [[projects]]
            id = "x"
            name = "X"
            path = "/abs/x"
        """), strict_remote_only=True)


def test_strict_remote_only_rejects_services(tmp_path):
    with pytest.raises(bd.ConfigError, match="remote-only"):
        bd.load_config(_write(tmp_path, """
            [[projects]]
            id = "x"
            name = "X"
            repo = "o/r"
            [projects.services]
            pm2 = ["x"]
        """), strict_remote_only=True)


NOW = datetime(2026, 7, 2, 12, 0, 0, tzinfo=timezone.utc)


def test_parse_ts_handles_z_suffix():
    assert bd.parse_ts("2026-07-02T10:00:00Z") == datetime(
        2026, 7, 2, 10, 0, 0, tzinfo=timezone.utc)
    assert bd.parse_ts(None) is None
    assert bd.parse_ts("garbage") is None


def test_relative_age():
    assert bd.relative_age(None, NOW) == ""
    assert bd.relative_age(NOW - timedelta(minutes=30), NOW) == "just now"
    assert bd.relative_age(NOW - timedelta(hours=3), NOW) == "3h ago"
    assert bd.relative_age(NOW - timedelta(days=2), NOW) == "2d ago"


def test_is_fresh_window():
    assert bd.is_fresh(NOW - timedelta(hours=10), NOW, 48) is True
    assert bd.is_fresh(NOW - timedelta(hours=60), NOW, 48) is False
    assert bd.is_fresh(None, NOW, 48) is False


def _live(**kw):
    base = dict(branch="main", version="v1.0.0", prs=2, issues=1, stars=42,
                ci="success", up=True, last_activity=NOW)
    base.update(kw)
    return base


def test_build_row_marks_new_within_window():
    row = bd.build_row({"id": "x", "name": "X", "repo": "o/x"},
                       _live(last_activity=NOW), NOW, fresh_hours=48)
    assert row["is_new"] is True
    assert row["age_label"] == "just now"


def test_build_row_placeholders_for_missing_data():
    row = bd.build_row({"id": "x", "name": "X", "repo": "o/x"},
                       {"last_activity": None}, NOW, fresh_hours=48)
    assert row["prs"] == "n/a"
    assert row["version"] == "(no tags)"
    assert row["is_new"] is False


def test_render_html_escapes_hostile_name():
    row = bd.build_row(
        {"id": "x", "name": "<img src=x onerror=alert(1)>", "repo": "o/x"},
        _live(), NOW, fresh_hours=48)
    html_out = bd.render_html([row], title="T")
    assert "<img src=x onerror=alert(1)>" not in html_out
    assert "&lt;img src=x onerror=alert(1)&gt;" in html_out


def test_render_html_escapes_repo_in_href():
    row = bd.build_row({"id": "x", "name": "X", "repo": 'o/x"><script>'},
                       _live(), NOW, fresh_hours=48)
    # bad repo would be rejected by validation, but render must still escape.
    html_out = bd.render_html([row], title="T")
    assert '"><script>' not in html_out


def test_render_html_no_env_omits_header():
    row = bd.build_row({"id": "x", "name": "X", "repo": "o/x"}, _live(), NOW, 48)
    with_env = bd.render_html([row], title="T", include_env=True,
                              env={"host": "runner", "note": "ENVLINE"})
    without = bd.render_html([row], title="T", include_env=False, env=None)
    assert "ENVLINE" in with_env
    assert "ENVLINE" not in without


def test_cli_demo_writes_dashboard(tmp_path):
    out = tmp_path / "dash.html"
    rc = bd.main(["--demo", "-o", str(out)])
    assert rc == 0
    html_out = out.read_text()
    assert "<!doctype html>" in html_out
    assert "Demo" in html_out  # at least one demo card title


def test_cli_dry_run_validates_without_output(tmp_path):
    cfg = tmp_path / "c.toml"
    cfg.write_text('[[projects]]\nid="x"\nname="X"\nrepo="o/x"\n')
    out = tmp_path / "should_not_exist.html"
    rc = bd.main(["--config", str(cfg), "--dry-run", "-o", str(out)])
    assert rc == 0
    assert not out.exists()


def test_run_cmd_missing_binary_returns_empty():
    assert bd.run_cmd(["definitely-not-a-real-binary-xyz"], timeout=2) == ""


def test_collect_local_missing_path_reports(monkeypatch):
    live = bd.collect_local({"id": "x", "name": "X", "path": "/no/such/dir"}, now=NOW)
    # No crash; branch unknown, last_activity None.
    assert live.get("last_activity") is None


def test_collect_local_parses_git(monkeypatch, tmp_path):
    calls = {}

    def fake_run(cmd, *, timeout, cwd=None):
        key = " ".join(cmd[:3])
        calls[key] = cmd
        if cmd[:2] == ["git", "branch"]:
            return "main"
        if cmd[:2] == ["git", "describe"]:
            return "v2.0.0"
        if cmd[:2] == ["git", "log"]:
            return "2026-07-02T09:00:00Z"
        return ""

    monkeypatch.setattr(bd, "run_cmd", fake_run)
    monkeypatch.setattr(bd.os.path, "isdir", lambda p: True)
    live = bd.collect_local({"id": "x", "name": "X", "path": str(tmp_path)}, now=NOW)
    assert live["branch"] == "main"
    assert live["version"] == "v2.0.0"
    assert live["last_activity"] == bd.parse_ts("2026-07-02T09:00:00Z")


SAMPLE_REPO = {
    "default_branch": "main", "stargazers_count": 128,
    "open_issues_count": 7, "pushed_at": "2026-07-02T08:00:00Z",
}


def test_parse_repo_json_maps_fields():
    live = bd.parse_repo_json(SAMPLE_REPO, prs=3, release_ts="2026-07-01T00:00:00Z")
    assert live["branch"] == "main"
    assert live["stars"] == 128
    assert live["prs"] == 3
    # issues count is total open (issues+PRs); we expose it as-is
    assert live["issues"] == 7
    assert live["last_activity"] == bd.parse_ts("2026-07-02T08:00:00Z")


def test_collect_live_dispatches_remote(monkeypatch):
    monkeypatch.setattr(bd, "collect_remote",
                        lambda p, *, token, now: {"branch": "REMOTE"})
    live = bd.collect_live({"id": "x", "name": "X", "repo": "o/x"}, token=None, now=NOW)
    assert live["branch"] == "REMOTE"


def test_collect_live_dispatches_local(monkeypatch):
    monkeypatch.setattr(bd, "collect_local", lambda p, *, now: {"branch": "LOCAL"})
    live = bd.collect_live({"id": "x", "name": "X", "path": "/p"}, token=None, now=NOW)
    assert live["branch"] == "LOCAL"


def test_example_config_is_remote_only():
    root = Path(__file__).resolve().parent.parent
    cfg = bd.load_config(str(root / "control-tower.config.example.toml"),
                         strict_remote_only=True)
    assert cfg["projects"], "example config must list at least one project"
    for p in cfg["projects"]:
        assert "path" not in p and "services" not in p
        assert bd.REPO_RE.match(p["repo"])
