from src.config_loader import load_config
from src.policy import SCREENSHOT_EXAMPLE_ACCOUNT, TAG_ACTIONS, VIEW_ACTIONS, inventory_policy, resource_groups_arn


def test_policy_matches_screenshot_sids_and_actions():
    policy = inventory_policy(partition="aws-us-gov", account_id=SCREENSHOT_EXAMPLE_ACCOUNT)
    assert policy["Version"] == "2012-10-17"
    view, tagging = policy["Statement"]
    assert view["Sid"] == "ViewSpecificResourceGroup"
    assert view["Effect"] == "Allow"
    assert view["Action"] == VIEW_ACTIONS
    assert view["Resource"] == "arn:aws-us-gov:resource-groups:*:053381801543:*/*"
    assert tagging["Sid"] == "TaggingReadOnly"
    assert tagging["Action"] == TAG_ACTIONS
    assert tagging["Resource"] == "*"


def test_resource_groups_arn_uses_target_account():
    assert resource_groups_arn("aws-us-gov", "999999999999") == "arn:aws-us-gov:resource-groups:*:999999999999:*/*"


def test_config_role_defaults():
    cfg = load_config()
    assert cfg.role.name == "r-edl-resource-inventory"
    assert cfg.partition == "aws-us-gov"
    assert any(spec.key == "Project Name" for spec in cfg.required_tags)
