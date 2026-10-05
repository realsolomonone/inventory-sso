# EDL resource inventory — 5-minute path

SSO login is the same as `~/workspace/s3-taggings`.

```bash
cd ~/workspace/inventory-sso
python3 edl_resource_inventory.py setup --install
source .venv/bin/activate
python edl_resource_inventory.py doctor
python edl_resource_inventory.py login --all
python edl_resource_inventory.py profiles --check
```

Then create and verify with Terragrunt:

```bash
cd infra/live/r-edl-resource-inventory
AWS_PROFILE=YOUR_PROFILE AWS_REGION=us-gov-east-1 terragrunt apply
terragrunt output verification
```

If a profile is still INVALID: `aws sso login --profile PROFILE-NAME`.
