# Read the role back from AWS after create and emit structured verification.

data "aws_iam_role" "verify" {
  name       = aws_iam_role.inventory.name
  depends_on = [aws_iam_role.inventory, aws_iam_role_policy.inventory]
}

locals {
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

  live_policy       = jsondecode(aws_iam_role_policy.inventory.policy)
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
  sso_trust_ok      = strcontains(data.aws_iam_role.verify.assume_role_policy, "sso.amazonaws.com") && strcontains(data.aws_iam_role.verify.assume_role_policy, "sts:AssumeRole")
  overall_pass      = local.view_ok && local.tagging_ok && local.arn_ok && local.sso_trust_ok

  verification_checks = [
    {
      name     = "Role exists"
      result   = "PASS"
      expected = var.role_name
      found    = data.aws_iam_role.verify.arn
    },
    {
      name     = "Trust allows IAM Identity Center"
      result   = local.sso_trust_ok ? "PASS" : "FAIL"
      expected = "sts:AssumeRole from aws-reserved/sso.amazonaws.com/*"
      found    = local.sso_trust_ok ? "sso.amazonaws.com present in assume-role policy" : "SSO trust not found"
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
      found    = join(", ", local.view_resources)
    },
    {
      name     = "Sid TaggingReadOnly"
      result   = local.tagging_ok ? "PASS" : "FAIL"
      expected = join(", ", sort(tolist(local.tagging_required)))
      found    = local.has_tagging ? join(", ", sort(tolist(local.tagging_actions))) : "(missing Sid)"
    },
  ]

  verification = {
    overall_status      = local.overall_pass ? "PASS" : "FAIL"
    account_id          = local.account_id
    partition           = local.partition
    role_name           = aws_iam_role.inventory.name
    role_arn            = data.aws_iam_role.verify.arn
    resource_groups_arn = local.resource_groups_arn
    checks              = local.verification_checks
  }

  verification_dir = var.verification_dir != "" ? var.verification_dir : path.cwd
}

check "live_role_matches_screenshot_policy" {
  assert {
    condition     = local.overall_pass
    error_message = "${var.role_name} in account ${local.account_id} is ${local.verification.overall_status}. See verification.json."
  }
}

resource "terraform_data" "compliance_gate" {
  count = var.fail_if_not_compliant ? 1 : 0
  lifecycle {
    precondition {
      condition     = local.overall_pass
      error_message = "${var.role_name} in account ${local.account_id} is ${local.verification.overall_status}. See verification.json."
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
