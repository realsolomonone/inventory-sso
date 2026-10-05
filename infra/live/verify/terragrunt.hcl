# Optional single-account data-only verify. All-account verify:
#   cd infra/live/verify-accounts && terragrunt run --all apply
#
#   AWS_PROFILE=YOUR_PROFILE AWS_REGION=us-gov-east-1 terragrunt apply
#   terragrunt output verification

include "root" {
  path = find_in_parent_folders("root.hcl")
}

terraform {
  source = "${get_parent_terragrunt_dir()}/../modules/verify-role"
}

inputs = {
  aws_profile      = get_env("AWS_PROFILE", "")
  verification_dir = get_terragrunt_dir()
}
