# Terragrunt control plane for every live unit (one stack per AWS account).
# Operators run `terragrunt run-all` from infra/live/accounts — not `terraform`.
# IAM resources live in infra/modules/*; this file wires provider, retries, and inputs.

locals {
  project                   = get_env("PROJECT", "inventory-sso")
  environment               = get_env("ENVIRONMENT", "gov-east")
  role_name                 = get_env("ROLE_NAME", "r-edl-resource-inventory")
  role_description          = get_env("ROLE_DESCRIPTION", "Read-only Resource Groups and Resource Groups Tagging API access for EDL inventory")
  aws_region                = get_env("AWS_REGION", "us-gov-east-1")
  purpose                   = get_env("PURPOSE", "edl-resource-inventory")
  project_name_tag          = get_env("PROJECT_NAME_TAG", "edl_resource_inventory")
  resource_group_account_id = get_env("RESOURCE_GROUP_ACCOUNT_ID", "")
  trusted_principal_arns    = compact([for v in split(",", get_env("TRUSTED_PRINCIPAL_ARNS", "")) : trimspace(v)])
  trusted_source_account_ids = compact([for v in split(",", get_env("TRUSTED_SOURCE_ACCOUNT_IDS", "")) : trimspace(v)])
  common_tags = {
    Environment    = local.environment
    Project        = local.project
    Purpose        = local.purpose
    "Project Name" = local.project_name_tag
    ManagedBy      = "terragrunt"
  }
}

retry_max_attempts       = 3
retry_sleep_interval_sec = 10
retryable_errors = [
  "(?s).*RequestLimitExceeded.*",
  "(?s).*Throttling.*",
  "(?s).*TooManyRequests.*",
  "(?s).*Client.RequestLimitExceeded.*",
]

terraform {
  source = "${get_parent_terragrunt_dir()}/../modules/r-edl-resource-inventory"

  extra_arguments "disable_input" {
    commands  = get_terraform_commands_that_need_input()
    arguments = ["-input=false"]
  }

  extra_arguments "lock_timeout" {
    commands  = get_terraform_commands_that_need_locking()
    arguments = ["-lock-timeout=20m"]
  }

  after_hook "show_verification" {
    commands     = ["apply"]
    execute      = ["terragrunt", "output", "verification"]
    working_dir  = get_terragrunt_dir()
    run_on_error = false
  }

  after_hook "show_verification_md" {
    commands     = ["apply"]
    execute      = ["sh", "-c", "f=$(terragrunt output -raw verification_md 2>/dev/null); [ -f \"$f\" ] && cat \"$f\""]
    working_dir  = get_terragrunt_dir()
    run_on_error = true
  }
}

# Provider lives here (not in the module) so every account stack is configured by Terragrunt.
generate "provider" {
  path      = "provider.tf"
  if_exists = "overwrite_terragrunt"
  contents  = <<EOF
provider "aws" {
  region  = var.aws_region
  profile = var.aws_profile == "" ? null : var.aws_profile
}

provider "local" {}
EOF
}

# Production remote state. Leave disabled until TG_STATE_BUCKET exists, then:
#   export TG_STATE_BUCKET=your-state-bucket
#   export TG_STATE_LOCK_TABLE=your-lock-table   # optional
#   export TG_STATE_PROFILE=sso-profile-for-state
#
# remote_state {
#   backend = "s3"
#   disable = get_env("TG_STATE_BUCKET", "") == ""
#   config = {
#     bucket  = get_env("TG_STATE_BUCKET", "placeholder")
#     key     = "${path_relative_to_include()}/terraform.tfstate"
#     region  = get_env("TG_STATE_REGION", get_env("AWS_REGION", "us-gov-east-1"))
#     encrypt = true
#     profile = get_env("TG_STATE_PROFILE", "")
#   }
#   generate = {
#     path      = "backend.tf"
#     if_exists = "overwrite_terragrunt"
#   }
# }
