# Optional single-account data-only verify. All-account verify:
#   cd infra/live/verify-accounts && terragrunt run-all apply
#
#   AWS_PROFILE=YOUR_PROFILE AWS_REGION=us-gov-east-1 terragrunt apply
#   terragrunt output verification

include "root" {
  path   = find_in_parent_folders("root.hcl")
  expose = true
}

terraform {
  source = "${get_parent_terragrunt_dir()}/../modules/verify-role"
}

inputs = {
  aws_profile               = get_env("AWS_PROFILE", "")
  aws_region                = include.root.locals.aws_region
  role_name                 = include.root.locals.role_name
  resource_group_account_id = include.root.locals.resource_group_account_id
  verification_dir          = get_terragrunt_dir()
  fail_if_not_compliant     = get_env("TG_FAIL_IF_NOT_COMPLIANT", "false") == "true"
}
