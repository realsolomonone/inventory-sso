# EDL resource inventory — r-edl-resource-inventory

Deploys IAM role **r-edl-resource-inventory** with Terragrunt, then optionally inventories tagged resources.

**Authenticate all accounts:** `./scripts/sso-login.sh --all`  
**Deploy all accounts:** `./scripts/run-all.sh apply --yes`  
**One account:** `AWS_PROFILE=NAME ./scripts/run-one.sh apply`

Python is **not** required for login, create, or verify. Accounts come from IAM Identity Center profiles in `~/.aws/config`. Project settings (role name, region, tags) come from `config/envs/` so this repo can be reused for another project or partition.

Run commands from this directory. AWS CLI v2, Terraform, and Terragrunt are required for apply.

---

## Quick path

```bash
cd ~/workspace/inventory-sso
./scripts/doctor.sh
./scripts/sso-login.sh --all
./scripts/sso-profiles.sh --check
./scripts/run-all.sh apply --yes
./scripts/run-all.sh output
```

If a profile is still **INVALID**: `aws sso login --profile PROFILE-NAME`.

---

## 1. Authenticate every account

```bash
./scripts/sso-login.sh --all
./scripts/sso-profiles.sh --check
```

That runs `aws sso login --profile NAME` once per Identity Center session (or start URL). Other profiles that share the session reuse the cached token. Static/access-key profiles are skipped.

| Goal | Command |
|------|---------|
| Every SSO profile | `./scripts/sso-login.sh --all` |
| Only expired sessions | `./scripts/sso-login.sh --only-expired` |
| Named profiles | `./scripts/sso-login.sh --profiles edl-addcp-dev-ew` |
| Login every profile (no session grouping) | `./scripts/sso-login.sh --all --per-profile` |
| Print commands only | `./scripts/sso-login.sh --all --dry-run` |
| One profile by hand | `aws sso login --profile PROFILE-NAME` |

The deploying profile must be allowed to create IAM roles (typically AdministratorAccess or an IAM-admin permission set).

---

## 2. Create + verify one account

```bash
AWS_PROFILE=YOUR_PROFILE ./scripts/run-one.sh plan
AWS_PROFILE=YOUR_PROFILE ./scripts/run-one.sh apply
```

Same thing with Terragrunt directly:

```bash
cd infra/live/create
AWS_PROFILE=YOUR_PROFILE AWS_REGION=us-gov-east-1 terragrunt apply
terragrunt output verification
```

Apply writes structured results to stdout, `verification.md`, and `verification.json`.

---

## 3. Create + verify every account

```bash
./scripts/stacks-generate.sh
./scripts/run-all.sh plan
./scripts/run-all.sh apply --yes
./scripts/run-all.sh output
```

`stacks-generate.sh` writes `infra/live/accounts/<profile>/terragrunt.hcl` for every matching SSO profile. `run-all.sh` generates stacks first if that directory is empty.

Run `terragrunt run-all` from `infra/live/accounts`, not from `infra/live`.

---

## 4. Verify later (no IAM writes)

One account:

```bash
AWS_PROFILE=YOUR_PROFILE ./scripts/run-one.sh verify
```

Every account (separate stacks, so Terragrunt state cannot destroy the role):

```bash
./scripts/run-all.sh verify
```

Overall status is `PASS`, `FAIL`, or `MISSING`. To fail CI when the role is missing or the policy does not match:

```bash
TG_FAIL_IF_NOT_COMPLIANT=true AWS_PROFILE=YOUR_PROFILE ./scripts/run-one.sh verify --yes
```

---

## Reuse for another project or environment

Copy an env file, change the role / region / tags, and pass `ENVIRONMENT` (or `ENV_FILE`) into the same scripts.

```bash
cp config/envs/commercial.example.env config/envs/commercial.env
# edit ROLE_NAME, AWS_REGION, AWS_PARTITION, PROJECT, PURPOSE, PROFILE_PREFIX, …

ENVIRONMENT=commercial ./scripts/sso-login.sh --all
ENVIRONMENT=commercial ./scripts/run-all.sh apply --yes
```

| Variable | What it changes |
|----------|-----------------|
| `ENVIRONMENT` | Which file under `config/envs/` is loaded (`gov-east` is default) |
| `ENV_FILE` | Explicit path, instead of `config/envs/$ENVIRONMENT.env` |
| `ROLE_NAME` | IAM role created in each account |
| `AWS_REGION` | Provider region |
| `AWS_PARTITION` | Documented partition (`aws-us-gov` or `aws`); live ARNs still come from the account |
| `PROFILE_PREFIX` | Only SSO profiles whose names start with this prefix |
| `SSO_START_URL` | Only profiles for this Identity Center start URL |
| `EXCLUDE_PROFILES` | Comma-separated profile names to skip |
| `RESOURCE_GROUP_ACCOUNT_ID` | Hub account in the Resource Groups ARN (empty = each target account) |
| `TRUSTED_PRINCIPAL_ARNS` | Extra assume-role ARNs (comma-separated) |
| `PROJECT`, `PURPOSE`, `PROJECT_NAME_TAG` | Tags on the IAM role |

Defaults live in `config/defaults.env`. Live units read these variables through Terragrunt `get_env`, so you do not hard-code a project name in the stacks.

---

## Cadence

| Step | Command |
|------|---------|
| Refresh SSO | `./scripts/sso-login.sh --all` |
| Check sessions | `./scripts/sso-profiles.sh --check` |
| Single-profile INVALID | `aws sso login --profile PROFILE-NAME` |
| Create + verify one account | `AWS_PROFILE=… ./scripts/run-one.sh apply` |
| Verify only | `AWS_PROFILE=… ./scripts/run-one.sh verify` |
| All accounts | `./scripts/run-all.sh apply --yes` |

---

## IAM policy (from the screenshot)

The Terraform module attaches this inline policy. The screenshot used account `053381801543` in the Resource Groups ARN. Each stack substitutes **that account’s ID** unless you set `RESOURCE_GROUP_ACCOUNT_ID`.

| Sid | Actions | Resource |
|-----|---------|----------|
| ViewSpecificResourceGroup | `resource-groups:GetGroup`, `GetGroupQuery`, `ListGroupResources`, `ListGroups`, `SearchResources` | `arn:PARTITION:resource-groups:*:<account>:*/*` |
| TaggingReadOnly | `tag:GetResources`, `tag:GetTagKeys`, `tag:GetTagValues` | `*` |

Trust: this account’s IAM Identity Center roles (`aws-reserved/sso.amazonaws.com/*`), plus optional extra ARNs.

Module: `infra/modules/r-edl-resource-inventory/`  
Verify (data-only): `infra/modules/verify-role/`  
Live units: `infra/live/create/`, `infra/live/verify/`

---

## Optional inventory scan (Python)

Scan reports still use Python. Skip this if you only need the IAM role.

```bash
python3 edl_resource_inventory.py setup --install
source .venv/bin/activate
python edl_resource_inventory.py scan
open reports/inventory-index-*.html
```

Scan is read-only. The only IAM write is Terragrunt apply on the create unit.

---

## Tests

Shell (login + stack generate, no AWS calls):

```bash
./scripts/sso-login.sh --all --dry-run
./scripts/doctor.sh
```

Optional Python tests:

```bash
source .venv/bin/activate
python -m pytest tests/ -q
```

---

## Security

- Trust is limited to IAM Identity Center roles (`aws-reserved/sso.amazonaws.com/*`).
- Policy is read-only (Resource Groups + tagging Get*).
- Do not commit `reports/`, generated `infra/live/accounts/*`, generated `infra/live/verify-accounts/*`, or live `verification.json` / `verification.md`.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| No profiles / INVALID | `./scripts/sso-login.sh --all` then `aws sso login --profile NAME` |
| AccessDenied on apply | Deploying SSO role needs `iam:CreateRole` / `iam:PutRolePolicy` |
| Verify overall `MISSING` | Run create apply first |
| AccessDenied on scan | Assume `r-edl-resource-inventory` or attach the same inline policy |
| run-all found extra stacks | Run from `infra/live/accounts`, not `infra/live` |
| No stacks generated | Add SSO profiles to `~/.aws/config` |
| Wrong accounts selected | Set `PROFILE_PREFIX`, `SSO_START_URL`, or `EXCLUDE_PROFILES` in the env file |
| terragrunt not on PATH | Install Terragrunt; `./scripts/doctor.sh` will FAIL until it is |
