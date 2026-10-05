output "role_name" {
  value = aws_iam_role.inventory.name
}

output "role_arn" {
  value = aws_iam_role.inventory.arn
}

output "resource_groups_arn" {
  value = local.resource_groups_arn
}

output "account_id" {
  value = local.account_id
}

output "partition" {
  value = local.partition
}

output "overall_status" {
  value = local.verification.overall_status
}

output "verification" {
  description = "Structured PASS/FAIL results for the live IAM role (screenshot policy)."
  value       = local.verification
}

output "verification_json" {
  value = "${local.verification_dir}/verification.json"
}

output "verification_md" {
  value = "${local.verification_dir}/verification.md"
}
