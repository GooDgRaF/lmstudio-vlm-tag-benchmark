from __future__ import annotations

from main import main
from tests.helpers import build_config


def test_validate_config_cli_success(tmp_path, capsys):
    config = build_config(tmp_path)
    rc = main(["validate-config", "--config", str(config)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "Config loaded" in out


def test_validate_config_cli_missing_file():
    try:
        main(["validate-config", "--config", "missing.yaml"])
    except SystemExit as exc:
        assert "does not exist" in str(exc)
    else:
        raise AssertionError("Expected SystemExit")

