from src.models import AccountVerify, VerifyReport
from src.policy import SCREENSHOT_EXAMPLE_ACCOUNT, VIEW_ACTIONS, inventory_policy
from src.verifier import evaluate_role, parse_iam_document


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
