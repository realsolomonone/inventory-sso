# Test plan — r-edl-resource-inventory

## L1 unit tests (no AWS)

```bash
source .venv/bin/activate
python -m pytest tests/ -q
```

| ID | Area | Expected |
|----|------|----------|
| UT-01 | SSO detection | SSO vs static |
| UT-02 | login --all dry-run | Only SSO profiles; `aws sso login --profile` |
| UT-03 | Policy document | Screenshot SIDs and actions |
| UT-04 | Role evaluate | PASS on screenshot policy, FAIL if SIDs missing |
| UT-05 | Stack generate | terragrunt.hcl contains profile + role name |

## L2 CLI / SSO (same as s3-taggings)

```bash
python edl_resource_inventory.py doctor
python edl_resource_inventory.py login --all --dry-run
python edl_resource_inventory.py login --all
python edl_resource_inventory.py profiles --check
```

## L3 Terragrunt

```bash
cd infra/live/r-edl-resource-inventory
AWS_PROFILE=YOUR_PROFILE AWS_REGION=us-gov-east-1 terragrunt apply
terragrunt output verification
```
