# EDL resource inventory — Terragrunt across all AWS accounts

Terragrunt project that creates IAM role **r-edl-resource-inventory** in every IAM Identity Center account.

**SSO (AWS CLI):** `./scripts/sso-login.sh --all`  
**All accounts:** `cd infra/live/accounts && terragrunt run-all apply`  
**One account:** `cd infra/live/accounts/<profile> && terragrunt apply`

Do not run `terraform` against this repo. Terragrunt generates the AWS provider and applies the IAM module per account. Python is optional (scan reports only).

Run from this directory. AWS CLI v2 and Terragrunt are required (Terragrunt calls the terraform binary).

---

## Quick path

```bash
cd ~/workspace/inventory-sso
./scripts/doctor.sh
./scripts/sso-login.sh --all
./scripts/sso-profiles.sh --check
./scripts/stacks-generate.sh

cd infra/live/accounts
terragrunt run-all plan
terragrunt run-all apply
terragrunt run-all output verification
```

If a profile is still **INVALID**: `aws sso login --profile PROFILE-NAME`.

Always run `run-all` from `infra/live/accounts` (or `infra/live/verify-accounts`), never from `infra/live`.

---

## 1. Authenticate every account

SSO is AWS CLI, not Terragrunt:

```bash
./scripts/sso-login.sh --all
./scripts/sso-profiles.sh --check
```

| Goal | Command |
|------|---------|
| Every SSO profile | `./scripts/sso-login.sh --all` |
| Only expired sessions | `./scripts/sso-login.sh --only-expired` |
| Named profiles | `./scripts/sso-login.sh --profiles edl-addcp-dev-ew` |
| Login every profile | `./scripts/sso-login.sh --all --per-profile` |
| Print commands only | `./scripts/sso-login.sh --all --dry-run` |
| One profile by hand | `aws sso login --profile PROFILE-NAME` |

The deploying permission set must be allowed to create IAM roles (typically AdministratorAccess).

---

## 2. Deploy every account (Terragrunt)

```bash
./scripts/stacks-generate.sh
cd infra/live/accounts
terragrunt run-all plan
terragrunt run-all apply
terragrunt run-all output verification
```

`stacks-generate.sh` writes `infra/live/accounts/<profile>/terragrunt.hcl` for each matching SSO profile. Each unit includes `infra/live/root.hcl` (provider, retries, tags, role name).

Convenience wrapper (same commands): `./scripts/run-all.sh apply --yes`

---

## 3. One account (Terragrunt)

After stacks exist:

```bash
cd infra/live/accounts/YOUR_PROFILE
terragrunt plan
terragrunt apply
terragrunt output verification
```

Without generating stacks, using `AWS_PROFILE`:

```bash
cd infra/live/create
AWS_PROFILE=YOUR_PROFILE AWS_REGION=us-gov-east-1 terragrunt apply
terragrunt output verification
```

Apply writes stdout (`terragrunt output verification`), `verification.md`, and `verification.json`.

---

## 4. Verify later (no IAM writes)

Every account (separate stacks so state cannot destroy the role):

```bash
./scripts/stacks-generate.sh --mode verify
cd infra/live/verify-accounts
terragrunt run-all apply
terragrunt run-all output verification
```

One account:

```bash
cd infra/live/verify
AWS_PROFILE=YOUR_PROFILE AWS_REGION=us-gov-east-1 terragrunt apply
terragrunt output verification
```

Overall status is `PASS`, `FAIL`, or `MISSING`. To fail CI:

```bash
TG_FAIL_IF_NOT_COMPLIANT=true AWS_PROFILE=YOUR_PROFILE terragrunt apply
```

---

## Reuse for another project or environment

Copy an env file, change role / region / tags, then run the same Terragrunt commands:

```bash
cp config/envs/commercial.example.env config/envs/commercial.env
ENVIRONMENT=commercial ./scripts/sso-login.sh --all
ENVIRONMENT=commercial ./scripts/stacks-generate.sh
cd infra/live/accounts
ENVIRONMENT=commercial terragrunt run-all apply
```

| Variable | What it changes |
|----------|-----------------|
| `ENVIRONMENT` | File under `config/envs/` (`gov-east` is default) |
| `ENV_FILE` | Explicit path instead of `config/envs/$ENVIRONMENT.env` |
| `ROLE_NAME` | IAM role created in each account |
| `AWS_REGION` | Provider region (Terragrunt `generate "provider"`) |
| `PROFILE_PREFIX` | Only SSO profiles whose names start with this prefix |
| `SSO_START_URL` | Only profiles for this Identity Center start URL |
| `EXCLUDE_PROFILES` | Comma-separated profile names to skip |
| `RESOURCE_GROUP_ACCOUNT_ID` | Hub account in the Resource Groups ARN (empty = target account) |
| `TRUSTED_PRINCIPAL_ARNS` | Extra assume-role ARNs (comma-separated) |
| `PROJECT`, `PURPOSE`, `PROJECT_NAME_TAG` | Tags on the IAM role |
| `TG_STATE_BUCKET` | Optional S3 remote state (uncomment `remote_state` in `root.hcl`) |

---

## Cadence

| Step | Command |
|------|---------|
| Refresh SSO | `./scripts/sso-login.sh --all` |
| Check sessions | `./scripts/sso-profiles.sh --check` |
| Generate live units | `./scripts/stacks-generate.sh` |
| Plan all accounts | `cd infra/live/accounts && terragrunt run-all plan` |
| Apply all accounts | `cd infra/live/accounts && terragrunt run-all apply` |
| One account | `cd infra/live/accounts/<profile> && terragrunt apply` |
| Verify all | `cd infra/live/verify-accounts && terragrunt run-all apply` |

---

## IAM policy (from the screenshot)

The module Terragrunt applies attaches this inline policy. The screenshot used account `053381801543`. Each stack substitutes **that account’s ID** unless you set `RESOURCE_GROUP_ACCOUNT_ID`.

| Sid | Actions | Resource |
|-----|---------|----------|
| ViewSpecificResourceGroup | `resource-groups:GetGroup`, `GetGroupQuery`, `ListGroupResources`, `ListGroups`, `SearchResources` | `arn:PARTITION:resource-groups:*:<account>:*/*` |
| TaggingReadOnly | `tag:GetResources`, `tag:GetTagKeys`, `tag:GetTagValues` | `*` |

Trust: this account’s IAM Identity Center roles (`aws-reserved/sso.amazonaws.com/*`), plus optional extra ARNs.

Terragrunt root: `infra/live/root.hcl`  
Create module: `infra/modules/r-edl-resource-inventory/`  
Verify module: `infra/modules/verify-role/`  
Live units: `infra/live/accounts/<profile>/`

---

## Optional inventory scan (Python)

```bash
python3 edl_resource_inventory.py setup --install
source .venv/bin/activate
python edl_resource_inventory.py scan
```

Scan is read-only. The only IAM write is `terragrunt apply` / `terragrunt run-all apply`.

---

## Tests

```bash
./scripts/sso-login.sh --all --dry-run
./scripts/doctor.sh
source .venv/bin/activate && python -m pytest tests/ -q
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
| run-all found extra stacks | Run from `infra/live/accounts`, not `infra/live` |
| No stacks generated | Add SSO profiles to `~/.aws/config`, then `./scripts/stacks-generate.sh` |
| Wrong accounts selected | Set `PROFILE_PREFIX`, `SSO_START_URL`, or `EXCLUDE_PROFILES` |
| terragrunt not on PATH | Install Terragrunt; `./scripts/doctor.sh` will FAIL until it is |
