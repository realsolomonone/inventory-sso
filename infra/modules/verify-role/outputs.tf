output "verification" {
  description = "Structured PASS/FAIL/MISSING results for the live IAM role (screenshot policy)."
  value       = local.verification
}

output "overall_status" {
  value = local.overall_status
}

output "role_arn" {
  value = local.role_arn
}

output "account_id" {
  value = local.account_id
}

output "partition" {
  value = local.partition
}

output "resource_groups_arn" {
  value = local.resource_groups_arn
}

output "verification_json" {
  value = "${local.verification_dir}/verification.json"
}

output "verification_md" {
  value = "${local.verification_dir}/verification.md"
}
