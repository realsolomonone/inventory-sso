from pathlib import Path

from src.sso_login import login_profiles


def test_python_login_all_dry_run_only_sso_profiles(tmp_path: Path, monkeypatch):
    aws = tmp_path / ".aws"
    aws.mkdir()
    (aws / "config").write_text(
        "[profile edl-uat]\n"
        "sso_start_url = https://example.awsapps.com/start\n"
        "sso_region = us-gov-east-1\n"
        "sso_account_id = 111111111111\n"
        "sso_role_name = Admin\n"
        "region = us-gov-east-1\n\n"
        "[profile static-keys]\n"
        "region = us-east-1\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("src.aws_profiles.Path.home", lambda: tmp_path)
    results = login_profiles(dry_run=True)
    by_name = {row.profile: row for row in results}
    assert by_name["edl-uat"].message == "DRY RUN: aws sso login --profile edl-uat"
    assert by_name["static-keys"].skipped
