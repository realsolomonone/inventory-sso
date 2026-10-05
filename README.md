# EDL resource inventory — Terragrunt across all AWS accounts

Terragrunt project that creates IAM role **r-edl-resource-inventory** in every IAM Identity Center account.

**SSO (AWS CLI):** `./scripts/sso-login.sh --all`  
**All accounts:** `cd infra/live/accounts && terragrunt run --all apply`  
**One account:** `cd infra/live/accounts/<profile> && terragrunt apply`

Current Terragrunt no longer has a `run-all` command. Use `terragrunt run --all …` (this is the CLI redesign). Do not run `terraform` against this repo.

Run from this directory. AWS CLI v2, Terragrunt, and **Terraform 1.5+** are required. On iebcloud, `terraform` on PATH is often **v0.12.31** — this project cannot use 0.12. Terragrunt calls `scripts/terraform-shim`, which looks for a 1.5+ binary. If none is found:

```bash
terraform version
module avail terraform
module load terraform/1.5
export TG_TF_PATH=$(command -v terraform)
./scripts/doctor.sh
```

---

## Quick path

```bash
cd ~/workspace/inventory-sso
./scripts/doctor.sh
./scripts/sso-login.sh --all
./scripts/sso-profiles.sh --check
./scripts/stacks-generate.sh

cd infra/live/accounts
terragrunt run --all plan
terragrunt run --all apply
terragrunt run --all output verification
```

If a profile is still **INVALID**: `aws sso login --profile PROFILE-NAME`.

Always run `--all` from `infra/live/accounts` (or `infra/live/verify-accounts`), never from `infra/live`.

If you see `unknown command: "run-all"`, you are on the new CLI. Use `terragrunt run --all plan`, not `terragrunt run-all plan`.

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
terragrunt run --all plan
terragrunt run --all apply
terragrunt run --all output verification
```

`stacks-generate.sh` writes `infra/live/accounts/<profile>/terragrunt.hcl` for each matching SSO profile. Each unit includes `infra/live/root.hcl` (provider, retries, tags, role name).

Convenience wrapper (detects new vs old CLI): `./scripts/run-all.sh apply --yes`

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

---

## 4. Verify later (no IAM writes)

```bash
./scripts/stacks-generate.sh --mode verify
cd infra/live/verify-accounts
terragrunt run --all apply
terragrunt run --all output verification
```

One account:

```bash
cd infra/live/verify
AWS_PROFILE=YOUR_PROFILE AWS_REGION=us-gov-east-1 terragrunt apply
terragrunt output verification
```

---

## 5. Destroy if you have to

Create stacks only (`infra/live/accounts`), never verify-accounts:

```bash
cd infra/live/accounts/YOUR_PROFILE
terragrunt run -- plan -destroy
terragrunt destroy
```

Every account:

```bash
cd infra/live/accounts
terragrunt run --all -- plan -destroy
terragrunt run --all destroy
```

Or: `./scripts/run-all.sh destroy --yes`

---

## Reuse for another project or environment

```bash
cp config/envs/commercial.example.env config/envs/commercial.env
ENVIRONMENT=commercial ./scripts/sso-login.sh --all
ENVIRONMENT=commercial ./scripts/stacks-generate.sh
cd infra/live/accounts
ENVIRONMENT=commercial terragrunt run --all apply
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
| Plan all accounts | `cd infra/live/accounts && terragrunt run --all plan` |
| Apply all accounts | `cd infra/live/accounts && terragrunt run --all apply` |
| One account | `cd infra/live/accounts/<profile> && terragrunt apply` |
| Verify all | `cd infra/live/verify-accounts && terragrunt run --all apply` |
| Destroy all | `cd infra/live/accounts && terragrunt run --all destroy` |

---

## IAM policy (from the screenshot)

The module Terragrunt applies attaches this inline policy. The screenshot used account `053381801543`. Each stack substitutes **that account’s ID** unless you set `RESOURCE_GROUP_ACCOUNT_ID`.

| Sid | Actions | Resource |
|-----|---------|----------|
| ViewSpecificResourceGroup | `resource-groups:GetGroup`, `GetGroupQuery`, `ListGroupResources`, `ListGroups`, `SearchResources` | `arn:PARTITION:resource-groups:*:<account>:*/*` |
| TaggingReadOnly | `tag:GetResources`, `tag:GetTagKeys`, `tag:GetTagValues` | `*` |

Trust: this account’s IAM Identity Center roles (`aws-reserved/sso.amazonaws.com/*`), plus optional extra ARNs.

Terragrunt root: `infra/live/root.hcl`  
Live units: `infra/live/accounts/<profile>/`

---

## Python environment + verify HTML report

These steps confirm **r-edl-resource-inventory** was created in every SSO account and write `reports/role-verify.html`. Do them in order. Skip nothing.

### What you need first

| Need | Check |
|------|--------|
| This repo on disk | `inventory-sso` (not only the overlay tarball) |
| Python 3.9+ | `python3 --version` |
| `venv` module | ships with Python; on some Linux: `python3 -m venv --help` |
| AWS CLI | `aws --version` |
| SSO profiles | `~/.aws/config` has `[profile …]` with `sso_start_url` |
| IAM role already applied | Terragrunt apply finished, or verify will report **missing** |

On iebcloud, load a modern Python if `python3` is too old:

```bash
python3 --version
module avail python
module load python/3.11
python3 --version
```

### 1. Go to the repo

```bash
cd ~/workspace/inventory-sso
```

Use your real path. Later commands must run from this directory.

### 2. Overlay files (only if you unpacked `inventory-sso-verify-docs.tar`)

If this checkout does not already have `python edl_resource_inventory.py verify --help`, copy from `python-verify/` onto the same paths:

```bash
cp python-verify/edl_resource_inventory.py ./edl_resource_inventory.py
cp python-verify/src/html_report.py ./src/html_report.py
cp python-verify/src/models.py ./src/models.py
cp python-verify/tests/test_html_report.py ./tests/test_html_report.py
cp python-verify/tests/test_verifier.py ./tests/test_verifier.py
```

Skip this step if you pulled `feature/inventory-sso-v1` and `verify --help` already works.

### 3. Create the virtual environment

**Option A (script):**

```bash
python3 edl_resource_inventory.py setup --install
```

**Option B (manual):**

```bash
python3 -m venv .venv
```

Windows: `py -3 -m venv .venv`

### 4. Activate it (every new terminal)

macOS / Linux / iebcloud:

```bash
source .venv/bin/activate
```

Windows (cmd): `.venv\Scripts\activate.bat`  
Windows (PowerShell): `.venv\Scripts\Activate.ps1`

You should see `(.venv)` in the prompt. Confirm:

```bash
which python
python --version
```

`which python` must point at `…/inventory-sso/.venv/bin/python`.

### 5. Install Python packages

If you used `setup --install`, packages are already installed. Otherwise:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

That installs `boto3`, `PyYAML`, and `pytest`. Confirm:

```bash
python -c "import boto3, yaml, pytest; print('python env ok')"
python edl_resource_inventory.py verify --help
```

You must see the `verify` subcommand. If `ModuleNotFoundError: boto3`, the venv is not active or step 5 was skipped.

### 6. Sign in to every SSO account

```bash
chmod +x scripts/*.sh
./scripts/sso-login.sh --all
./scripts/sso-profiles.sh --check
```

Every profile you care about must be **VALID**. If one is **INVALID**:

```bash
aws sso login --profile PROFILE-NAME
./scripts/sso-profiles.sh --check
```

### 7. Run verify

Still in the repo, venv still active:

```bash
python edl_resource_inventory.py verify --open
```

That command:

1. Reads SSO profiles from `~/.aws/config`
2. Checks STS credentials
3. Calls IAM `GetRole` / `GetRolePolicy` in each account
4. Checks: role exists, SSO trust, `ViewSpecificResourceGroup`, Resource Groups ARN, `TaggingReadOnly`
5. Writes `reports/role-verify.html` (also JSON/CSV next to it)
6. `--open` launches the HTML in your default browser

If the browser does not open:

```bash
ls -l reports/role-verify.html
open reports/role-verify.html
```

iebcloud / Linux:

```bash
firefox reports/role-verify.html
# or copy the file to your laptop and open it locally
```

Read the banner: **ALL ACCOUNTS PASS**, **PARTIAL**, or **FAIL**. Expand each account for per-check results.

### 8. Useful verify options

```bash
# One profile only
python edl_resource_inventory.py verify --profiles YOUR_PROFILE --open

# Faster (IAM only, skip tag:GetTagKeys probe)
python edl_resource_inventory.py verify --no-probe --open

# Write files without opening a browser
python edl_resource_inventory.py verify

# Machine-readable
python edl_resource_inventory.py verify --format json
```

Exit codes: `0` all pass, `1` partial, `2` fail / no valid profiles.

### 9. Optional tagged-resource scan (not the same as verify)

```bash
python edl_resource_inventory.py scan
```

---

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
| `unknown command: "run-all"` | Use `terragrunt run --all plan` (new CLI). Do not use `terragrunt run-all`. |
| `retryable_errors` / `expose` parse errors | Pull latest `feature/inventory-sso-v1`, then **regenerate** stacks: `./scripts/stacks-generate.sh` |
| Terraform version check failed / `0.12.31` is not compatible with `>= 1.5.0` | PATH terraform is 0.12. Load 1.5+: `module avail terraform` then `module load terraform/1.5`, or `export TG_TF_PATH=/path/to/terraform`. Confirm with `./scripts/doctor.sh`. |
| extra stacks found | Run from `infra/live/accounts`, not `infra/live` |
| No profiles / INVALID | `./scripts/sso-login.sh --all` then `aws sso login --profile NAME` |
| AccessDenied on apply | Deploying SSO role needs `iam:CreateRole` / `iam:PutRolePolicy` |
| Verify overall `MISSING` | Run create apply first |
| No stacks generated | Add SSO profiles to `~/.aws/config`, then `./scripts/stacks-generate.sh` |
| Wrong accounts selected | Set `PROFILE_PREFIX`, `SSO_START_URL`, or `EXCLUDE_PROFILES` |
| terragrunt not on PATH | Install Terragrunt; `./scripts/doctor.sh` will FAIL until it is |
| `python3: command not found` | Install Python 3.9+ or `module load python/3.11` |
| `ensurepip` / `venv` missing | `python3 -m venv .venv` failed; install `python3-venv` (Linux) or another Python |
| `ModuleNotFoundError: boto3` | `source .venv/bin/activate` then `python -m pip install -r requirements.txt` |
| `verify` is not a known command | Overlay/pull latest `feature/inventory-sso-v1`; run `python edl_resource_inventory.py verify --help` |
| No valid profiles / all SKIP | `./scripts/sso-login.sh --all` then `./scripts/sso-profiles.sh --check` |
| HTML not found | Run verify from the repo root with venv on; file is `reports/role-verify.html` |
