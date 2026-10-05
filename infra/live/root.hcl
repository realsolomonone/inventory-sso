# Shared Terragrunt config for r-edl-resource-inventory.
# Create stacks inherit terraform.source from here. The verify live unit overrides it.

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

# Optional remote state. Uncomment and set the bucket after it exists.
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
