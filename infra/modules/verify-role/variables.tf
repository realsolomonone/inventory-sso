variable "aws_region" {
  type        = string
  description = "Provider region (GovCloud home is typically us-gov-east-1)."
  default     = "us-gov-east-1"
}

variable "aws_profile" {
  type        = string
  description = "AWS CLI / Identity Center profile used to read the live IAM role."
  default     = ""
}

variable "role_name" {
  type    = string
  default = "r-edl-resource-inventory"
}

variable "resource_group_account_id" {
  type        = string
  description = "Expected account ID in the Resource Groups ARN. Empty = caller account."
  default     = ""
}

variable "verification_dir" {
  type        = string
  description = "Directory for verification.json and verification.md."
  default     = ""
}

variable "fail_if_not_compliant" {
  type        = bool
  description = "If true, terraform apply fails when the live role is missing or does not match the screenshot policy."
  default     = false
}
