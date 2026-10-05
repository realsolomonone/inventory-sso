# Create (and verify) the inventory IAM role in the account for AWS_PROFILE.
# Role name / region / tags come from config/envs/*.env — not hard-coded.
#
#   ./scripts/sso-login.sh --all
#   AWS_PROFILE=YOUR_PROFILE ./scripts/run-one.sh apply
#   AWS_PROFILE=YOUR_PROFILE AWS_REGION=us-gov-east-1 terragrunt apply

include "root" {
  path   = find_in_parent_folders("root.hcl")
  expose = true
}

inputs = {
  aws_profile               = get_env("AWS_PROFILE", "")
  aws_region                = include.root.locals.aws_region
  role_name                 = include.root.locals.role_name
  role_description          = include.root.locals.role_description
  resource_group_account_id = include.root.locals.resource_group_account_id
  trusted_principal_arns    = include.root.locals.trusted_principal_arns
  trusted_source_account_ids = include.root.locals.trusted_source_account_ids
  tags                      = include.root.locals.common_tags
  verification_dir          = get_terragrunt_dir()
  fail_if_not_compliant     = get_env("TG_FAIL_IF_NOT_COMPLIANT", "false") == "true"
}
