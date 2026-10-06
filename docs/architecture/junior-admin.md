# Junior admin demo

Never run `terraform` here. Never use `terragrunt run-all` (old). Use `terragrunt run --all` from `infra/live/accounts`.

## Deploy

```bash
cd ~/workspace/inventory-sso
./scripts/doctor.sh
./scripts/sso-login.sh --all
./scripts/sso-profiles.sh --check
./scripts/stacks-generate.sh
cd infra/live/accounts
terragrunt run --all plan
terragrunt run --all apply
```

If terraform is 0.12: `module load terraform/1.5` then `export TG_TF_PATH=$(command -v terraform)`.

## Verify

```bash
./scripts/verify.sh
```

Show `reports/executive.html`. If a row failed, open `reports/role-verify.html`.

INVALID profile: `aws sso login --profile NAME`  
MISSING role: apply first, then verify again.
