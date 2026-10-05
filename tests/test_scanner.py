from src.config_loader import load_config
from src.models import AccountStatus, TagHealth
from src.scanner import _record_from_mapping, run_inventory
from src.tags import score_tags


class FakeTagging:
    def __init__(self, mappings):
        self.mappings = mappings

    def get_resources(self, **kwargs):
        return {"ResourceTagMappingList": self.mappings, "PaginationToken": ""}


class FakeRG:
    def list_groups(self, **kwargs):
        return {"Groups": [{"GroupArn": "arn:aws-us-gov:resource-groups:us-gov-east-1:111:group/demo", "Name": "demo"}]}


class FakeSTS:
    def get_caller_identity(self):
        return {"Account": "111111111111", "Arn": "arn:aws-us-gov:iam::111111111111:user/test"}


class FakeSession:
    def __init__(self, mappings):
        self.mappings = mappings

    def client(self, name, region_name=None):
        if name == "sts":
            return FakeSTS()
        if name == "resourcegroupstaggingapi":
            return FakeTagging(self.mappings)
        if name == "resource-groups":
            return FakeRG()
        raise AssertionError(name)


def test_record_scores_missing_edl_tags():
    cfg = load_config()
    record = _record_from_mapping(
        {
            "ResourceARN": "arn:aws-us-gov:s3:::v-s3-edl-demo",
            "Tags": [{"Key": "Environment", "Value": "dev"}],
        },
        profile="edl-uat",
        account_id="111",
        account_name="edl-uat",
        catalog_environment="uat",
        partition="aws-us-gov",
        partition_label="AWS GovCloud (US)",
        region="us-gov-east-1",
        config=cfg,
    )
    assert record.service == "s3"
    assert record.health in {TagHealth.PARTIAL, TagHealth.UNTAGGED}
    assert "Project Name" in record.missing_tags


def test_run_inventory_with_fake_session():
    cfg = load_config()
    mappings = [
        {
            "ResourceARN": "arn:aws-us-gov:lambda:us-gov-east-1:111:function:fn",
            "Tags": [
                {"Key": "Project Name", "Value": "edl_abcd"},
                {"Key": "ProjectNumber", "Value": "fs0000000001"},
                {"Key": "Organization", "Value": "census:ocio:adsd"},
                {"Key": "CostAllocation", "Value": "adsd:edl"},
                {"Key": "Environment", "Value": "dev"},
                {"Key": "Project Role", "Value": "edl_abcd_xyz"},
                {"Key": "edl:project_id", "Value": "9999999"},
                {"Key": "Title Data", "Value": "title_13"},
                {"Key": "boc:created_by", "Value": "abcde001"},
            ],
        }
    ]

    def factory(profile):
        return FakeSession(mappings)

    inventory = run_inventory(cfg, ["edl-uat"], session_factory=factory)
    assert inventory.accounts[0].status == AccountStatus.OK
    assert inventory.resources_total == 1
    assert inventory.resources_complete == 1
    assert inventory.accounts[0].groups_total == 1


def test_complete_tags_score_100():
    cfg = load_config()
    expected = {spec.key: spec.example for spec in cfg.required_tags}
    health, pct = score_tags(expected, cfg.required_tags)
    assert health == TagHealth.COMPLETE
    assert pct == 100.0
