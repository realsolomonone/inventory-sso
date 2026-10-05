from datetime import datetime, timezone
from pathlib import Path

from src.config_loader import load_config
from src.html_report import write_html_reports, write_verify_html_reports
from src.models import AccountResult, AccountStatus, AccountVerify, CheckResult, Inventory, ResourceRecord, TagHealth, VerifyReport
from src.reports import write_data_reports, write_verify_reports
from src.scanner import build_narrative


def test_html_and_csv_include_role_name(tmp_path: Path):
    cfg = load_config()
    inventory = Inventory(
        ticket=cfg.ticket,
        program=cfg.program,
        title=cfg.title,
        generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        accounts=[
            AccountResult(
                profile="edl-uat",
                account_id="111111111111",
                account_name="edl-uat",
                catalog_environment="uat",
                partition="aws-us-gov",
                partition_label="AWS GovCloud (US)",
                status=AccountStatus.OK,
                resources_total=1,
                resources_complete=1,
            )
        ],
        records=[
            ResourceRecord(
                profile="edl-uat",
                account_id="111111111111",
                account_name="edl-uat",
                catalog_environment="uat",
                partition="aws-us-gov",
                partition_label="AWS GovCloud (US)",
                region="us-gov-east-1",
                service="s3",
                resource_type="bucket",
                resource_arn="arn:aws-us-gov:s3:::v-s3-edl-demo",
                health=TagHealth.COMPLETE,
                completeness_pct=100.0,
                missing_tags=[],
                invalid_tags=[],
                extra_tags={},
                expected={"Project Name": "edl_abcd"},
                all_tags={"Project Name": "edl_abcd"},
            )
        ],
        required_tags=cfg.required_tags,
    )
    inventory.narrative = build_narrative(inventory)
    reports = write_data_reports(inventory, tmp_path)
    inventory.reports = reports
    html = write_html_reports(inventory, tmp_path)
    text = Path(html["executive_html"]).read_text(encoding="utf-8")
    assert "r-edl-resource-inventory" in text
    assert "edl-uat" in Path(reports["accounts_csv"]).read_text(encoding="utf-8")
    assert "v-s3-edl-demo" in Path(reports["inventory_csv"]).read_text(encoding="utf-8")


def test_verify_html_is_ready_to_open(tmp_path: Path):
    report = VerifyReport(
        generated_at="2026-10-05 20:00:00 UTC",
        role_name="r-edl-resource-inventory",
        ticket="EDL-RESOURCE-INVENTORY",
        accounts=[
            AccountVerify(
                profile="edl-uat",
                account_id="111111111111",
                account_name="edl-uat",
                partition="aws-us-gov",
                role_name="r-edl-resource-inventory",
                role_arn="arn:aws-us-gov:iam::111111111111:role/r-edl-resource-inventory",
                created="2026-10-01 12:00:00 UTC",
                status="pass",
                checks=[CheckResult(name="Role exists", passed=True, expected="r-edl-resource-inventory", found="r-edl-resource-inventory")],
            ),
            AccountVerify(
                profile="edl-dev",
                account_id="222222222222",
                account_name="edl-dev",
                partition="aws-us-gov",
                role_name="r-edl-resource-inventory",
                status="missing",
                message="Role does not exist",
                checks=[CheckResult(name="Role exists", passed=False, expected="r-edl-resource-inventory", found="(missing)")],
            ),
        ],
        narrative=["1 pass, 0 fail, 1 missing."],
    )
    paths = write_verify_reports(report, tmp_path)
    report.reports = paths
    html = write_verify_html_reports(report, tmp_path)
    latest = Path(html["verify_html"])
    assert latest.name == "role-verify.html"
    text = latest.read_text(encoding="utf-8")
    assert text.startswith("<!DOCTYPE html>")
    assert "r-edl-resource-inventory" in text
    assert "edl-uat" in text
    assert "edl-dev" in text
    assert "PARTIAL" in text
    assert "Role exists" in text
    assert Path(html["verify_html_archive"]).is_file()
    exec_path = Path(html["executive_html"])
    assert exec_path.name == "executive.html"
    exec_text = exec_path.read_text(encoding="utf-8")
    assert "executive verification" in exec_text.lower() or "Accounts that need attention" in exec_text
    assert "edl-dev" in exec_text
