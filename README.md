# EDL resource inventory — r-edl-resource-inventory

Deploys IAM role **r-edl-resource-inventory** with Terragrunt, then optionally inventories tagged resources.

Accounts come from `~/.aws/config` (same SSO login as s3-taggings). Run every command from this directory. Python 3.9+.

---

## How to use

### 1. One-time setup

```bash
cd ~/workspace/inventory-sso
python3 edl_resource_inventory.py setup --install
source .venv/bin/activate
python edl_resource_inventory.py doctor
```

Every `doctor` line should say **PASS**. If imports fail, you are not in the venv.

### 2. Log in to every account

Same contract as `python edl_s3_tag_inventory.py login --all`:

```bash
python edl_resource_inventory.py login --all
python edl_resource_inventory.py profiles --check
python edl_resource_inventory.py accounts
```

If a profile is still **INVALID**:

```bash
aws sso login --profile PROFILE-NAME
```

Useful variants: `login --only-expired` or `login --profiles edl-addcp-dev-ew`.

### 3. Create + verify (Terragrunt)

```bash
cd infra/live/r-edl-resource-inventory
AWS_PROFILE=YOUR_PROFILE AWS_REGION=us-gov-east-1 terragrunt apply
terragrunt output verification
```

Apply creates the role and writes `verification.md` / `verification.json`.

Verify later with no IAM writes:

```bash
cd infra/live/verify
AWS_PROFILE=YOUR_PROFILE AWS_REGION=us-gov-east-1 terragrunt apply
terragrunt output verification
```

Fail CI when the role is missing or the policy does not match the screenshot:

```bash
TG_FAIL_IF_NOT_COMPLIANT=true AWS_PROFILE=YOUR_PROFILE terragrunt apply
```

### 4. Every SSO account

```bash
cd infra/live/accounts
terragrunt run-all apply
terragrunt run-all output verification
```

Each account needs a `terragrunt.hcl` (copy `infra/live/account.hcl.example`, or `python edl_resource_inventory.py stacks generate`).

---

## IAM policy (from the screenshot)

The Terraform module attaches this inline policy. The screenshot used account `053381801543` in the Resource Groups ARN. Each stack substitutes **that account’s ID** unless you set `RESOURCE_GROUP_ACCOUNT_ID`.

| Sid | Actions | Resource |
|-----|---------|----------|
| ViewSpecificResourceGroup | `resource-groups:GetGroup`, `GetGroupQuery`, `ListGroupResources`, `ListGroups`, `SearchResources` | `arn:aws-us-gov:resource-groups:*:<account>:*/*` |
| TaggingReadOnly | `tag:GetResources`, `tag:GetTagKeys`, `tag:GetTagValues` | `*` |

Trust: this account’s IAM Identity Center roles (`aws-reserved/sso.amazonaws.com/*`).

---

## Optional inventory scan

```bash
python edl_resource_inventory.py scan
open reports/inventory-index-*.html
```

Scan is read-only. The only IAM write is `terragrunt apply` on the create unit.
