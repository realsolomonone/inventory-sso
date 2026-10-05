# Data-only: read r-edl-resource-inventory from AWS and write structured results.
# Does not create or change the IAM role.

data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

data "aws_iam_roles" "lookup" {
  name_regex = "^${var.role_name}$"
}

locals {
  role_found = length(data.aws_iam_roles.lookup.names) > 0
}

data "aws_iam_role" "verify" {
  count = local.role_found ? 1 : 0
  name  = var.role_name
}

data "external" "inline_policy" {
  count   = local.role_found ? 1 : 0
  program = ["python3", "${path.module}/read_inline_policy.py"]
  query = {
    role_name   = var.role_name
    policy_name = "${var.role_name}-policy"
    profile     = var.aws_profile
    region      = var.aws_region
  }
}

locals {
  account_id                = data.aws_caller_identity.current.account_id
  partition                 = data.aws_partition.current.partition
  resource_group_account_id = var.resource_group_account_id != "" ? var.resource_group_account_id : local.account_id
  resource_groups_arn       = "arn:${local.partition}:resource-groups:*:${local.resource_group_account_id}:*/*"

  view_required = toset([
    "resource-groups:GetGroup",
    "resource-groups:GetGroupQuery",
    "resource-groups:ListGroupResources",
    "resource-groups:ListGroups",
    "resource-groups:SearchResources",
  ])
  tagging_required = toset([
    "tag:GetResources",
    "tag:GetTagKeys",
    "tag:GetTagValues",
  ])

  policy_found      = local.role_found && try(data.external.inline_policy[0].result.found, "false") == "true"
  policy_error      = local.role_found ? try(data.external.inline_policy[0].result.error, "") : ""
  live_policy       = local.policy_found ? jsondecode(data.external.inline_policy[0].result.policy) : { Statement = [] }
  live_statements   = try(local.live_policy.Statement, [])
  view_list         = [for s in local.live_statements : s if try(s.Sid, "") == "ViewSpecificResourceGroup"]
  tagging_list      = [for s in local.live_statements : s if try(s.Sid, "") == "TaggingReadOnly"]
  has_view          = length(local.view_list) == 1
  has_tagging       = length(local.tagging_list) == 1
  view_actions      = local.has_view ? toset(flatten([local.view_list[0].Action])) : toset([])
  tagging_actions   = local.has_tagging ? toset(flatten([local.tagging_list[0].Action])) : toset([])
  view_resources    = local.has_view ? flatten([local.view_list[0].Resource]) : []
  tagging_resources = local.has_tagging ? flatten([local.tagging_list[0].Resource]) : []
  view_ok           = local.has_view && setintersection(local.view_required, local.view_actions) == local.view_required
  tagging_ok        = local.has_tagging && setintersection(local.tagging_required, local.tagging_actions) == local.tagging_required && contains(local.tagging_resources, "*")
  arn_ok            = contains(local.view_resources, local.resource_groups_arn)
  assume_policy     = local.role_found ? data.aws_iam_role.verify[0].assume_role_policy : ""
  sso_trust_ok      = strcontains(local.assume_policy, "sso.amazonaws.com") && strcontains(local.assume_policy, "sts:AssumeRole")
  role_arn          = local.role_found ? data.aws_iam_role.verify[0].arn : ""
  overall_pass      = local.role_found && local.policy_found && local.view_ok && local.tagging_ok && local.arn_ok && local.sso_trust_ok
  overall_status    = local.role_found ? (local.overall_pass ? "PASS" : "FAIL") : "MISSING"

  verification_checks = [
    {
      name     = "Role exists"
      result   = local.role_found ? "PASS" : "FAIL"
      expected = var.role_name
      found    = local.role_found ? local.role_arn : "(not found)"
    },
    {
      name     = "Inline policy exists"
      result   = local.policy_found ? "PASS" : "FAIL"
      expected = "${var.role_name}-policy"
      found    = local.policy_found ? "${var.role_name}-policy" : (local.policy_error != "" ? local.policy_error : "(missing)")
    },
    {
      name     = "Trust allows IAM Identity Center"
      result   = local.sso_trust_ok ? "PASS" : "FAIL"
      expected = "sts:AssumeRole from aws-reserved/sso.amazonaws.com/*"
      found    = local.sso_trust_ok ? "sso.amazonaws.com present in assume-role policy" : (local.role_found ? "SSO trust not found" : "(role missing)")
    },
    {
      name     = "Sid ViewSpecificResourceGroup"
      result   = local.view_ok ? "PASS" : "FAIL"
      expected = join(", ", sort(tolist(local.view_required)))
      found    = local.has_view ? join(", ", sort(tolist(local.view_actions))) : "(missing Sid)"
    },
    {
      name     = "Resource Groups ARN"
      result   = local.arn_ok ? "PASS" : "FAIL"
      expected = local.resource_groups_arn
      found    = length(local.view_resources) > 0 ? join(", ", local.view_resources) : "(none)"
    },
    {
      name     = "Sid TaggingReadOnly"
      result   = local.tagging_ok ? "PASS" : "FAIL"
      expected = join(", ", sort(tolist(local.tagging_required)))
      found    = local.has_tagging ? join(", ", sort(tolist(local.tagging_actions))) : "(missing Sid)"
    },
  ]

  verification = {
    overall_status      = local.overall_status
    account_id          = local.account_id
    partition           = local.partition
    role_name           = var.role_name
    role_arn            = local.role_arn
    resource_groups_arn = local.resource_groups_arn
    checks              = local.verification_checks
  }

  verification_dir = var.verification_dir != "" ? var.verification_dir : path.cwd
}

check "live_role_matches_screenshot_policy" {
  assert {
    condition     = local.overall_pass
    error_message = "${var.role_name} in account ${local.account_id} is ${local.overall_status}. See verification.json."
  }
}

resource "terraform_data" "compliance_gate" {
  count = var.fail_if_not_compliant ? 1 : 0
  lifecycle {
    precondition {
      condition     = local.overall_pass
      error_message = "${var.role_name} in account ${local.account_id} is ${local.overall_status}. See verification.json."
    }
  }
}

resource "local_file" "verification_json" {
  filename = "${local.verification_dir}/verification.json"
  content  = jsonencode(local.verification)
}

resource "local_file" "verification_md" {
  filename = "${local.verification_dir}/verification.md"
  content  = templatefile("${path.module}/verification.md.tftpl", local.verification)
}
