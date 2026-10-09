from src.config_loader import load_config
from src.models import AccountVerify, VerifyReport
from src.policy import SCREENSHOT_EXAMPLE_ACCOUNT, VIEW_ACTIONS, inventory_policy
from src.tags import example_tags
from src.verifier import evaluate_edl_tags, evaluate_role, parse_iam_document


def test_parse_iam_document_url_encoded():
    raw = "%7B%22Version%22%3A%222012-10-17%22%7D"
    assert parse_iam_document(raw)["Version"] == "2012-10-17"


def test_evaluate_role_matches_screenshot_policy():
    policy = inventory_policy(partition="aws-us-gov", account_id=SCREENSHOT_EXAMPLE_ACCOUNT)
    trust = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AllowSSOAssume",
                "Effect": "Allow",
                "Action": ["sts:AssumeRole", "sts:TagSession"],
                "Condition": {"ArnLike": {"aws:PrincipalArn": ["arn:aws-us-gov:iam::053381801543:role/aws-reserved/sso.amazonaws.com/*"]}},
            }
        ],
    }
    checks = evaluate_role(
        {"RoleName": "r-edl-resource-inventory", "Arn": "arn:aws-us-gov:iam::053381801543:role/r-edl-resource-inventory"},
        trust,
        policy,
        role_name="r-edl-resource-inventory",
        account_id=SCREENSHOT_EXAMPLE_ACCOUNT,
        partition="aws-us-gov",
        resource_group_account_id=SCREENSHOT_EXAMPLE_ACCOUNT,
    )
    assert all(item.passed for item in checks)
    assert checks[2].expected.split(", ")[0] == VIEW_ACTIONS[0]


def test_evaluate_role_fails_when_sid_missing():
    checks = evaluate_role(
        {"RoleName": "r-edl-resource-inventory", "Arn": "arn:aws-us-gov:iam::1:role/r-edl-resource-inventory"},
        {},
        {"Statement": []},
        role_name="r-edl-resource-inventory",
        account_id="1",
        partition="aws-us-gov",
        resource_group_account_id="1",
    )
    by_name = {item.name: item for item in checks}
    assert by_name["Trust allows IAM Identity Center"].passed is False
    assert by_name["Sid ViewSpecificResourceGroup"].passed is False
    assert by_name["Sid TaggingReadOnly"].passed is False


def test_verify_report_overall_status():
    def _row(profile: str, status: str) -> AccountVerify:
        return AccountVerify(
            profile=profile,
            account_id="1",
            account_name=profile,
            partition="aws-us-gov",
            role_name="r-edl-resource-inventory",
            status=status,
        )

    empty = VerifyReport(generated_at="now", role_name="r", ticket="t", accounts=[])
    assert empty.overall_status == "empty"
    passed = VerifyReport(generated_at="now", role_name="r", ticket="t", accounts=[_row("a", "pass")])
    assert passed.overall_status == "pass"
    mixed = VerifyReport(
        generated_at="now",
        role_name="r",
        ticket="t",
        accounts=[_row("a", "pass"), _row("b", "missing")],
    )
    assert mixed.overall_status == "partial"
    failed = VerifyReport(generated_at="now", role_name="r", ticket="t", accounts=[_row("a", "fail")])
    assert failed.overall_status == "fail"


def _screenshot_trust():
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "AllowSSOAssume",
                "Effect": "Allow",
                "Action": ["sts:AssumeRole", "sts:TagSession"],
                "Condition": {"ArnLike": {"aws:PrincipalArn": ["arn:aws-us-gov:iam::053381801543:role/aws-reserved/sso.amazonaws.com/*"]}},
            }
        ],
    }


def test_evaluate_role_edl_tags_pass():
    cfg = load_config()
    policy = inventory_policy(partition="aws-us-gov", account_id=SCREENSHOT_EXAMPLE_ACCOUNT)
    checks = evaluate_role(
        {"RoleName": "r-edl-resource-inventory", "Arn": "arn:aws-us-gov:iam::053381801543:role/r-edl-resource-inventory"},
        _screenshot_trust(),
        policy,
        role_name="r-edl-resource-inventory",
        account_id=SCREENSHOT_EXAMPLE_ACCOUNT,
        partition="aws-us-gov",
        resource_group_account_id=SCREENSHOT_EXAMPLE_ACCOUNT,
        role_tags=example_tags(cfg.required_tags),
        tag_specs=cfg.required_tags,
    )
    assert all(item.passed for item in checks)


def test_evaluate_role_edl_tags_fail_gov_east_and_missing():
    cfg = load_config()
    policy = inventory_policy(partition="aws-us-gov", account_id=SCREENSHOT_EXAMPLE_ACCOUNT)
    checks = evaluate_role(
        {"RoleName": "r-edl-resource-inventory", "Arn": "arn:aws-us-gov:iam::053381801543:role/r-edl-resource-inventory"},
        _screenshot_trust(),
        policy,
        role_name="r-edl-resource-inventory",
        account_id=SCREENSHOT_EXAMPLE_ACCOUNT,
        partition="aws-us-gov",
        resource_group_account_id=SCREENSHOT_EXAMPLE_ACCOUNT,
        role_tags={"Environment": "gov-east", "Project Name": "edl_resource_inventory"},
        tag_specs=cfg.required_tags,
    )
    by_name = {item.name: item for item in checks}
    assert by_name["EDL compliance tags"].passed is False
    assert by_name["Tag Environment"].passed is False
    assert by_name["Tag ProjectNumber"].passed is False


def test_evaluate_edl_tags_list_error():
    cfg = load_config()
    checks = evaluate_edl_tags({}, cfg.required_tags, tag_error="AccessDenied listing role tags")
    assert len(checks) == 1
    assert checks[0].passed is False
