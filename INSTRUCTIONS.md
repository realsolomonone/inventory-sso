# EDL resource inventory — instructions

Canonical runbook: authenticate with the same SSO contract as s3-taggings, then deploy **r-edl-resource-inventory** with Terragrunt.

Accounts are **not** hard-coded. The tool reads every profile in `~/.aws/config`.

---

## 1. Setup

```bash
cd ~/workspace/inventory-sso
python3 edl_resource_inventory.py setup --install
source .venv/bin/activate
python edl_resource_inventory.py doctor
```

Install Terraform and Terragrunt before apply. `doctor` still PASSes without them so you can log in and generate stacks.

---

## 2. SSO (same as s3-taggings)

```bash
python edl_resource_inventory.py login --all
python edl_resource_inventory.py profiles --check
python edl_resource_inventory.py accounts
```

That runs `aws sso login --profile NAME` for every Identity Center profile. Static/access-key profiles are skipped.

If a profile is still INVALID:

```bash
aws sso login --profile PROFILE-NAME
```

Variants: `login --only-expired` or `login --profiles edl-addcp-dev-ew`.

The deploying profile must be allowed to create IAM roles (typically AdministratorAccess or an IAM-admin permission set).

---

## 3. Create the role (Terragrunt)

```bash
cd infra/live/r-edl-resource-inventory
AWS_PROFILE=YOUR_PROFILE AWS_REGION=us-gov-east-1 terragrunt plan
AWS_PROFILE=YOUR_PROFILE AWS_REGION=us-gov-east-1 terragrunt apply
terragrunt output verification
```

Results:

- stdout after apply (`terraform output verification`)
- `verification.md`
- `verification.json`

---

## 4. Verify later (Terragrunt, no IAM writes)

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

## 5. Every SSO account

Copy `infra/live/account.hcl.example` to `infra/live/accounts/<profile>/terragrunt.hcl` and set `aws_profile`, or:

```bash
python edl_resource_inventory.py stacks generate
cd infra/live/accounts
terragrunt run-all apply
terragrunt run-all output verification
```

Run `run-all` from `infra/live/accounts`, not from `infra/live`.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| No profiles / INVALID | `python edl_resource_inventory.py login --all` then `aws sso login --profile NAME` |
| AccessDenied on apply | Deploying SSO role needs `iam:CreateRole` / `iam:PutRolePolicy` |
| Verify overall `MISSING` | Run create apply first |
| run-all found extra stacks | Run from `infra/live/accounts` |
