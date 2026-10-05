# EDL resource inventory — runbook

**Role:** `r-edl-resource-inventory`  
**SSO:** `python edl_resource_inventory.py login --all` (same as s3-taggings)  
**Deploy:** `terragrunt apply`  
**Verify:** `terragrunt apply` in `infra/live/verify` or `terragrunt output verification` after create

## Cadence

| Step | Command |
|------|---------|
| Refresh SSO | `python edl_resource_inventory.py login --all` |
| Check sessions | `python edl_resource_inventory.py profiles --check` |
| Single-profile INVALID | `aws sso login --profile PROFILE-NAME` |
| Create + verify one account | `cd infra/live/r-edl-resource-inventory && AWS_PROFILE=… terragrunt apply` |
| Verify only | `cd infra/live/verify && AWS_PROFILE=… terragrunt apply` |
| All accounts | add units under `infra/live/accounts/`, then `run-all apply` |

## Security

- Trust is limited to IAM Identity Center roles (`aws-reserved/sso.amazonaws.com/*`).
- Policy is read-only (Resource Groups + tagging Get*).
- Do not commit `reports/`, verification files, or generated `infra/live/accounts/*`.
