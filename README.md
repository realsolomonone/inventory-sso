# EDL resource inventory — r-edl-resource-inventory

Deploys IAM role **r-edl-resource-inventory** with Terragrunt, then optionally inventories tagged resources.

**SSO:** `python edl_resource_inventory.py login --all` (same as s3-taggings)  
**Deploy:** `terragrunt apply`  
**Verify:** `terragrunt apply` in `infra/live/verify`, or `terragrunt output verification` after create

Accounts are **not** hard-coded. Every command uses IAM Identity Center profiles in `~/.aws/config`. Run from this directory. Python 3.9+. Terraform and Terragrunt are required for apply.

---

## Quick path

```bash
cd ~/workspace/inventory-sso
python3 edl_resource_inventory.py setup --install
source .venv/bin/activate
python edl_resource_inventory.py doctor
python edl_resource_inventory.py login --all
python edl_resource_inventory.py profiles --check

cd infra/live/r-edl-resource-inventory
AWS_PROFILE=YOUR_PROFILE AWS_REGION=us-gov-east-1 terragrunt apply
terragrunt output verification
```

If a profile is still **INVALID**: `aws sso login --profile PROFILE-NAME`.

---

## 1. Setup

```bash
cd ~/workspace/inventory-sso
python3 edl_resource_inventory.py setup --install
source .venv/bin/activate
python edl_resource_inventory.py doctor
```

Every `doctor` line should say **PASS**. If imports fail, you are not in the venv. Install Terraform and Terragrunt before apply; `doctor` still PASSes without them so you can log in and generate stacks.

---

## 2. Log in to every account (same as s3-taggings)

```bash
python edl_resource_inventory.py login --all
python edl_resource_inventory.py profiles --check
python edl_resource_inventory.py accounts
```

That runs `aws sso login --profile NAME` for every Identity Center profile. Static/access-key profiles are skipped.

If a profile is still **INVALID**:

```bash
aws sso login --profile PROFILE-NAME
```

Variants: `login --only-expired` or `login --profiles edl-addcp-dev-ew`.

The deploying profile must be allowed to create IAM roles (typically AdministratorAccess or an IAM-admin permission set).

---

## 3. Create + verify (Terragrunt)

```bash
cd infra/live/r-edl-resource-inventory
AWS_PROFILE=YOUR_PROFILE AWS_REGION=us-gov-east-1 terragrunt plan
AWS_PROFILE=YOUR_PROFILE AWS_REGION=us-gov-east-1 terragrunt apply
terragrunt output verification
```

Apply creates the role and writes structured results:

- stdout (`terraform output verification`)
- `verification.md`
- `verification.json`

---

## 4. Verify later (no IAM writes)

```bash
cd infra/live/verify
AWS_PROFILE=YOUR_PROFILE AWS_REGION=us-gov-east-1 terragrunt apply
terragrunt output verification
```

Overall status is `PASS`, `FAIL`, or `MISSING`. To fail CI when the role is missing or the policy does not match the screenshot:

```bash
TG_FAIL_IF_NOT_COMPLIANT=true AWS_PROFILE=YOUR_PROFILE terragrunt apply
```

---

## 5. Every SSO account

```bash
cd infra/live/accounts
terragrunt run-all apply
terragrunt run-all output verification
```

Each account needs a `terragrunt.hcl`. Copy `infra/live/account.hcl.example` to `infra/live/accounts/<profile>/terragrunt.hcl` and set `aws_profile`, or:

```bash
python edl_resource_inventory.py stacks generate
cd infra/live/accounts
terragrunt run-all apply
terragrunt run-all output verification
```

Run `run-all` from `infra/live/accounts`, not from `infra/live`.

---

## Cadence

| Step | Command |
|------|---------|
| Refresh SSO | `python edl_resource_inventory.py login --all` |
| Check sessions | `python edl_resource_inventory.py profiles --check` |
| Single-profile INVALID | `aws sso login --profile PROFILE-NAME` |
| Create + verify one account | `cd infra/live/r-edl-resource-inventory && AWS_PROFILE=… terragrunt apply` |
| Verify only | `cd infra/live/verify && AWS_PROFILE=… terragrunt apply` |
| All accounts | add units under `infra/live/accounts/`, then `run-all apply` |

---

## IAM policy (from the screenshot)

The Terraform module attaches this inline policy. The screenshot used account `053381801543` in the Resource Groups ARN. Each stack substitutes **that account’s ID** unless you set `RESOURCE_GROUP_ACCOUNT_ID`.

| Sid | Actions | Resource |
|-----|---------|----------|
| ViewSpecificResourceGroup | `resource-groups:GetGroup`, `GetGroupQuery`, `ListGroupResources`, `ListGroups`, `SearchResources` | `arn:aws-us-gov:resource-groups:*:<account>:*/*` |
| TaggingReadOnly | `tag:GetResources`, `tag:GetTagKeys`, `tag:GetTagValues` | `*` |

Trust: this account’s IAM Identity Center roles (`aws-reserved/sso.amazonaws.com/*`), plus optional extra ARNs.

Module: `infra/modules/r-edl-resource-inventory/`  
Verify (data-only): `infra/modules/verify-role/`  
Live units: `infra/live/r-edl-resource-inventory/`, `infra/live/verify/`

---

## Optional inventory scan

```bash
python edl_resource_inventory.py scan
open reports/inventory-index-*.html
```

Scan is read-only. The only IAM write is `terragrunt apply` on the create unit.

Optional evidence upload: `python edl_resource_inventory.py upload reports/ --bucket BUCKET`

---

## Tests

```bash
source .venv/bin/activate
python -m pytest tests/ -q
python edl_resource_inventory.py selftest
```

| ID | Area | Expected |
|----|------|----------|
| UT-01 | SSO detection | SSO vs static |
| UT-02 | login --all dry-run | Only SSO profiles; `aws sso login --profile` |
| UT-03 | Policy document | Screenshot SIDs and actions |
| UT-04 | Role evaluate | PASS on screenshot policy, FAIL if SIDs missing |
| UT-05 | Stack generate | terragrunt.hcl contains profile + role name |

CLI / SSO (same as s3-taggings):

```bash
python edl_resource_inventory.py doctor
python edl_resource_inventory.py login --all --dry-run
python edl_resource_inventory.py login --all
python edl_resource_inventory.py profiles --check
```

---

## Security

- Trust is limited to IAM Identity Center roles (`aws-reserved/sso.amazonaws.com/*`).
- Policy is read-only (Resource Groups + tagging Get*).
- Do not commit `reports/`, generated `infra/live/accounts/*`, or live `verification.json` / `verification.md`.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| No profiles / INVALID | `python edl_resource_inventory.py login --all` then `aws sso login --profile NAME` |
| AccessDenied on apply | Deploying SSO role needs `iam:CreateRole` / `iam:PutRolePolicy` |
| Verify overall `MISSING` | Run create apply first |
| AccessDenied on scan | Assume `r-edl-resource-inventory` or attach the same inline policy |
| run-all found extra stacks | Run from `infra/live/accounts`, not `infra/live` |
| No stacks generated | Add SSO profiles to `~/.aws/config` |
| terragrunt not on PATH | Install Terragrunt; login and doctor still work without it |
