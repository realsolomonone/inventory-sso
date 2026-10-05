data "aws_caller_identity" "current" {}
data "aws_partition" "current" {}

locals {
  account_id                = data.aws_caller_identity.current.account_id
  partition                 = data.aws_partition.current.partition
  resource_group_account_id = var.resource_group_account_id != "" ? var.resource_group_account_id : local.account_id
  resource_groups_arn       = "arn:${local.partition}:resource-groups:*:${local.resource_group_account_id}:*/*"
  sso_role_arn_this_account = "arn:${local.partition}:iam::${local.account_id}:role/aws-reserved/sso.amazonaws.com/*"
  sso_role_arns_extra       = [for id in var.trusted_source_account_ids : "arn:${local.partition}:iam::${id}:role/aws-reserved/sso.amazonaws.com/*"]
  assume_arn_likes          = concat([local.sso_role_arn_this_account], local.sso_role_arns_extra, var.trusted_principal_arns)
  common_tags = merge(
    {
      Name           = var.role_name
      ManagedBy      = "terragrunt"
      Purpose        = "edl-resource-inventory"
      "Project Name" = "edl_resource_inventory"
    },
    var.tags,
  )
}

data "aws_iam_policy_document" "trust" {
  statement {
    sid     = "AllowSSOAssume"
    effect  = "Allow"
    actions = ["sts:AssumeRole", "sts:TagSession"]

    principals {
      type        = "AWS"
      identifiers = ["arn:${local.partition}:iam::${local.account_id}:root"]
    }

    condition {
      test     = "ArnLike"
      variable = "aws:PrincipalArn"
      values   = local.assume_arn_likes
    }
  }
}

# Matches the screenshot policy: ViewSpecificResourceGroup + TaggingReadOnly.
# Resource Groups ARN is parameterized per account instead of hard-coding 053381801543.
data "aws_iam_policy_document" "inventory" {
  statement {
    sid    = "ViewSpecificResourceGroup"
    effect = "Allow"
    actions = [
      "resource-groups:GetGroup",
      "resource-groups:GetGroupQuery",
      "resource-groups:ListGroupResources",
      "resource-groups:ListGroups",
      "resource-groups:SearchResources",
    ]
    resources = [local.resource_groups_arn]
  }

  statement {
    sid    = "TaggingReadOnly"
    effect = "Allow"
    actions = [
      "tag:GetResources",
      "tag:GetTagKeys",
      "tag:GetTagValues",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role" "inventory" {
  name                 = var.role_name
  description          = var.role_description
  max_session_duration = var.max_session_duration
  assume_role_policy   = data.aws_iam_policy_document.trust.json
  tags                 = local.common_tags
}

resource "aws_iam_role_policy" "inventory" {
  name   = "${var.role_name}-policy"
  role   = aws_iam_role.inventory.id
  policy = data.aws_iam_policy_document.inventory.json
}
