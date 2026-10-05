from pathlib import Path

from src.aws_profiles import (
    describe_profile,
    list_aws_profiles,
    list_sso_profiles,
    profile_is_sso,
)


def _write_config(path: Path, content: str) -> None:
    aws_dir = path / ".aws"
    aws_dir.mkdir()
    (aws_dir / "config").write_text(content, encoding="utf-8")


def test_profile_is_sso_detects_sso_and_non_sso(tmp_path: Path, monkeypatch):
    _write_config(
        tmp_path,
        "[default]\nregion = us-gov-east-1\n\n"
        "[profile sso-account]\n"
        "sso_start_url = https://example.awsapps.com/start\n"
        "sso_region = us-gov-east-1\n"
        "sso_account_id = 053381801543\n"
        "sso_role_name = AuditRole\n"
        "region = us-gov-east-1\n\n"
        "[profile static-account]\n"
        "region = us-gov-east-1\n",
    )
    monkeypatch.setattr("src.aws_profiles.Path.home", lambda: tmp_path)

    assert profile_is_sso("sso-account") is True
    assert profile_is_sso("static-account") is False
    assert list_sso_profiles() == ["sso-account"]
    assert list_aws_profiles() == ["default", "sso-account", "static-account"]
    assert describe_profile("sso-account").account_id == "053381801543"
