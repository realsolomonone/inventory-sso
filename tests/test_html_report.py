from datetime import datetime, timezone
from pathlib import Path

from src.config_loader import load_config
from src.html_report import write_html_reports
from src.models import AccountResult, AccountStatus, Inventory, ResourceRecord, TagHealth
from src.reports import write_data_reports
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
