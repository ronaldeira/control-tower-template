# tests/test_dashboard.py
import textwrap
import pytest
import build_dashboard as bd
from datetime import datetime, timezone, timedelta


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
