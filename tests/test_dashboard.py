# tests/test_dashboard.py
import textwrap
import pytest
import build_dashboard as bd


def _write(tmp_path, toml_text):
    p = tmp_path / "cfg.toml"
    p.write_text(textwrap.dedent(toml_text))
    return str(p)


def test_mode_of_detects_local_and_remote():
    assert bd.mode_of({"id": "a", "path": "/x"}) == "local"
    assert bd.mode_of({"id": "a", "repo": "o/r"}) == "remote"


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
