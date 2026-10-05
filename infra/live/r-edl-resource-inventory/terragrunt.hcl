# Same as ../create. Prefer infra/live/accounts + terragrunt run --all for every account.

include "root" {
  path = find_in_parent_folders("root.hcl")
}

inputs = {
  aws_profile      = get_env("AWS_PROFILE", "")
  verification_dir = get_terragrunt_dir()
}
