# Shared Terragrunt config. Role name, region, tags, and partition come from
# config/envs/*.env (exported by scripts/*.sh) so this stack is reusable.

locals {
  project              = get_env("PROJECT", "inventory-sso")
  environment          = get_env("ENVIRONMENT", "gov-east")
  role_name            = get_env("ROLE_NAME", "r-edl-resource-inventory")
  role_description     = get_env("ROLE_DESCRIPTION", "Read-only Resource Groups and Resource Groups Tagging API access for EDL inventory")
  aws_region           = get_env("AWS_REGION", "us-gov-east-1")
  purpose              = get_env("PURPOSE", "edl-resource-inventory")
  project_name_tag     = get_env("PROJECT_NAME_TAG", "edl_resource_inventory")
  resource_group_account_id = get_env("RESOURCE_GROUP_ACCOUNT_ID", "")
  trusted_principal_arns     = compact([for v in split(",", get_env("TRUSTED_PRINCIPAL_ARNS", "")) : trimspace(v)])
  trusted_source_account_ids = compact([for v in split(",", get_env("TRUSTED_SOURCE_ACCOUNT_IDS", "")) : trimspace(v)])
  common_tags = {
    Environment    = local.environment
    Project        = local.project
    Purpose        = local.purpose
    "Project Name" = local.project_name_tag
    ManagedBy      = "terragrunt"
  }
}

terraform {
  source = "${get_parent_terragrunt_dir()}/../modules/r-edl-resource-inventory"

  after_hook "show_verification" {
    commands     = ["apply"]
    execute      = ["terraform", "output", "verification"]
    run_on_error = false
  }

  after_hook "show_verification_md" {
    commands     = ["apply"]
    execute      = ["sh", "-c", "f=$(terraform output -raw verification_md 2>/dev/null); [ -f \"$f\" ] && cat \"$f\""]
    run_on_error = true
  }
}

# Optional remote state. Uncomment and set TG_STATE_BUCKET after it exists.
# remote_state {
#   backend = "s3"
#   config = {
#     bucket  = get_env("TG_STATE_BUCKET", "YOUR-STATE-BUCKET")
#     key     = "${path_relative_to_include()}/terraform.tfstate"
#     region  = get_env("AWS_REGION", "us-gov-east-1")
#     encrypt = true
#     profile = get_env("TG_STATE_PROFILE", "")
#   }
#   generate = {
#     path      = "backend.tf"
#     if_exists = "overwrite_terragrunt"
#   }
# }
