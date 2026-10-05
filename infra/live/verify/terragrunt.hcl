# Read-only verification of the live r-edl-resource-inventory role.
# Does not create or change IAM. Writes verification.json and verification.md.
#
#   aws sso login --profile YOUR_PROFILE
#   AWS_PROFILE=YOUR_PROFILE AWS_REGION=us-gov-east-1 terragrunt apply
#   terragrunt output verification

include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "${get_parent_terragrunt_dir()}/../modules/verify-role"
}

inputs = {
  aws_profile               = get_env("AWS_PROFILE", "")
  aws_region                = get_env("AWS_REGION", "us-gov-east-1")
  role_name                 = get_env("INVENTORY_ROLE_NAME", "r-edl-resource-inventory")
  resource_group_account_id = get_env("RESOURCE_GROUP_ACCOUNT_ID", "")
  verification_dir          = get_terragrunt_dir()
  fail_if_not_compliant     = get_env("TG_FAIL_IF_NOT_COMPLIANT", "false") == "true"
}
