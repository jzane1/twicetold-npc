"""Required database checks fail closed; setup failures still release scratch state."""

import subprocess
import traceback
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

import conftest
import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict


def request_for(required):
    return SimpleNamespace(config=SimpleNamespace(getoption=lambda _: required))


@pytest.mark.parametrize(
    "ci,required", [("true", True), ("1", True), ("FALSE", False), ("", False)]
)
def test_ci_enables_required_database_by_default(monkeypatch, ci, required):
    monkeypatch.setenv("CI", ci)
    parser = Mock()
    conftest.pytest_addoption(parser)
    assert parser.addoption.call_args.args == ("--require-db",)
    assert parser.addoption.call_args.kwargs["default"] is required


@pytest.mark.parametrize("missing", [True, False])
@pytest.mark.parametrize("required", [True, False])
def test_database_unavailable_fails_in_required_mode_without_leaking_uri(
    monkeypatch, missing, required
):
    monkeypatch.setattr(
        conftest,
        "_base_uri",
        lambda: None if missing else "postgresql://user:private@localhost/app",
    )
    connect = Mock(side_effect=psycopg.OperationalError("private connection details"))
    monkeypatch.setattr(conftest.psycopg, "connect", connect)
    fixture = conftest.suite_env.__wrapped__(request_for(required))
    if required:
        with pytest.raises(pytest.fail.Exception) as error:
            next(fixture)
    else:
        with pytest.warns(UserWarning), pytest.raises(pytest.skip.Exception) as error:
            next(fixture)
    assert "private" not in str(error.value)
    if required:
        assert "private" not in "".join(traceback.format_exception(error.value))
    assert connect.call_count == (0 if missing else 1)


@pytest.mark.parametrize(
    "outcome", ["success", "migration_failure", "migration_timeout"]
)
def test_scratch_cleanup_runs_after_success_and_failed_migration(monkeypatch, outcome):
    base = "postgresql://user:private@localhost/product?dbname=product"
    monkeypatch.setattr(conftest, "_base_uri", lambda: base)
    admin, cleanup = MagicMock(), MagicMock()
    admin.__enter__.return_value = admin
    cleanup.__enter__.return_value = cleanup
    connect = Mock(side_effect=[admin, cleanup])
    monkeypatch.setattr(conftest.psycopg, "connect", connect)
    migration = Mock(
        return_value=SimpleNamespace(
            returncode=0 if outcome == "success" else 1,
            stdout="",
            stderr="migration failure",
        )
    )
    if outcome == "migration_timeout":
        migration.side_effect = subprocess.TimeoutExpired(["migration", base], 120)
    monkeypatch.setattr(conftest.subprocess, "run", migration)
    fixture = conftest.suite_env.__wrapped__(request_for(True))
    if outcome == "success":
        env = next(fixture)
        assert conninfo_to_dict(env.database_uri)["dbname"] == conftest.SUITE_DB
        assert env.settings.provider_mode == "fake"
        fixture.close()
    else:
        with pytest.raises(pytest.fail.Exception) as error:
            next(fixture)
        assert "private" not in "".join(traceback.format_exception(error.value))
    assert all(
        conninfo_to_dict(call.args[0])["dbname"] == "postgres"
        for call in connect.call_args_list
    )
    commands = [call.args[0] for call in admin.execute.call_args_list]
    assert commands == [
        f"DROP DATABASE IF EXISTS {conftest.SUITE_DB} WITH (FORCE)",
        f"CREATE DATABASE {conftest.SUITE_DB}",
    ]
    cleanup.execute.assert_called_once_with(
        f"DROP DATABASE IF EXISTS {conftest.SUITE_DB} WITH (FORCE)"
    )
    migration_uri = migration.call_args.args[0][-1]
    assert conninfo_to_dict(migration_uri)["dbname"] == conftest.SUITE_DB
