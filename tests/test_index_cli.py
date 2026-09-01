import json

import pytest

from axiolex import index_cli


def test_cli_returns_machine_readable_error(monkeypatch, capsys):
    monkeypatch.setattr(
        index_cli.ToolIndexingService,
        "status",
        lambda self: (_ for _ in ()).throw(RuntimeError("Redis is unavailable")),
    )
    monkeypatch.setattr(
        "sys.argv",
        ["axiolex-index", "status"],
    )

    with pytest.raises(SystemExit) as exc:
        index_cli.main()

    assert exc.value.code == 1
    error = json.loads(capsys.readouterr().err)
    assert error == {
        "success": False,
        "error": "RuntimeError",
        "message": "Redis is unavailable",
    }


def test_refresh_requires_caller_owned_configuration_paths(monkeypatch, capsys, tmp_path):
    monkeypatch.delenv("AXIOLEX_TOOLS_FILE", raising=False)
    monkeypatch.delenv("AXIOLEX_MCP_PROVIDERS_FILE", raising=False)
    # Point _shipped_source_dir at an empty temp dir so no shipped files are found
    monkeypatch.setattr(index_cli, "_shipped_source_dir", lambda: "")
    monkeypatch.setattr("sys.argv", ["axiolex-index", "refresh"])

    with pytest.raises(SystemExit) as exc:
        index_cli.main()

    assert exc.value.code == 1
    error = json.loads(capsys.readouterr().err)
    assert error["error"] == "ValueError"
    assert "--tools-file and --providers-file" in error["message"]
