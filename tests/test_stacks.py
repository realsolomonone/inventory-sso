from pathlib import Path

from src.config_loader import load_config
from src.stacks import generate_stacks, stack_slug


def test_stack_slug_sanitizes():
    assert stack_slug("edl-uat") == "edl-uat"
    assert stack_slug("profile name") == "profile-name"


def test_generate_stacks_writes_terragrunt(tmp_path: Path, monkeypatch):
    aws = tmp_path / ".aws"
    aws.mkdir()
    (aws / "config").write_text(
        "[profile edl-uat]\n"
        "sso_start_url = https://example.awsapps.com/start\n"
        "sso_region = us-gov-east-1\n"
        "sso_account_id = 111111111111\n"
        "sso_role_name = Admin\n"
        "region = us-gov-east-1\n",
        encoding="utf-8",
    )
    monkeypatch.setattr("src.aws_profiles.Path.home", lambda: tmp_path)
    cfg = load_config()
    out = tmp_path / "accounts"
    paths = generate_stacks(["edl-uat"], cfg, accounts_dir=out, clean=True)
    assert len(paths) == 1
    text = paths[0].read_text(encoding="utf-8")
    assert 'aws_profile               = "edl-uat"' in text
    assert "111111111111" in text
    assert 'include "root"' in text
    assert "expose" not in text
    assert "include.root.locals" not in text
    assert "verification_dir          = get_terragrunt_dir()" in text
    assert "terragrunt run --all" in text
    assert "terragrunt apply" in text


def test_root_hcl_is_terragrunt_control_plane():
    root = Path(__file__).resolve().parents[1] / "infra" / "live" / "root.hcl"
    text = root.read_text(encoding="utf-8")
    assert 'generate "provider"' in text
    assert "terragrunt run --all" in text
    assert "extra_arguments" in text
    assert "retry_max_attempts" not in text
    assert "retryable_errors =" not in text
    assert "expose = true" not in text
    assert 'execute      = ["terraform"' not in text
    assert "role_name" in text
    assert "terraform-shim" in text
    assert "terraform_version_constraint" in text
    assert ">= 1.5.0" in text
