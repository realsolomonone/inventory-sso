from pathlib import Path
from unittest.mock import patch

from src.sso_login import login_profiles


def _write_config(tmp_path: Path) -> None:
    aws = tmp_path / ".aws"
    aws.mkdir()
    (aws / "config").write_text(
        "\n".join(
            [
                "[default]",
                "region = us-east-1",
                "",
                "[profile edl-uat]",
                "sso_start_url = https://example.awsapps.com/start",
                "sso_region = us-gov-east-1",
                "sso_account_id = 111111111111",
                "sso_role_name = AuditRole",
                "region = us-gov-east-1",
                "",
                "[profile static-keys]",
                "region = us-east-1",
            ]
        ),
        encoding="utf-8",
    )


def test_login_all_dry_run_only_sso_profiles(tmp_path: Path, monkeypatch):
    _write_config(tmp_path)
    monkeypatch.setattr("src.aws_profiles.Path.home", lambda: tmp_path)
    results = login_profiles(dry_run=True)
    by_name = {r.profile: r for r in results}
    assert by_name["edl-uat"].message.startswith("DRY RUN: aws sso login --profile edl-uat")
    assert by_name["static-keys"].skipped


def test_login_runs_aws_cli_for_sso(tmp_path: Path, monkeypatch):
    _write_config(tmp_path)
    monkeypatch.setattr("src.aws_profiles.Path.home", lambda: tmp_path)

    class _Done:
        returncode = 0

    with patch("src.sso_login.subprocess.run", return_value=_Done()) as mocked:
        results = login_profiles(["edl-uat", "static-keys"], dry_run=False)

    assert mocked.call_count == 1
    assert mocked.call_args.args[0] == ["aws", "sso", "login", "--profile", "edl-uat"]
    assert results[0].ok and results[0].attempted
    assert results[1].skipped
