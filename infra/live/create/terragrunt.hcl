# Optional single-account unit when AWS_PROFILE is already set.
# All-account deploys use infra/live/accounts + `terragrunt run --all`.
#
#   AWS_PROFILE=YOUR_PROFILE AWS_REGION=us-gov-east-1 terragrunt apply
#   terragrunt output verification

include "root" {
  path = find_in_parent_folders("root.hcl")
}

inputs = {
  aws_profile      = get_env("AWS_PROFILE", "")
  verification_dir = get_terragrunt_dir()
}
