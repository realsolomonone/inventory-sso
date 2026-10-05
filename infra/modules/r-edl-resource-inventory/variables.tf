variable "aws_region" {
  type        = string
  description = "Provider region (set by Terragrunt; GovCloud home is typically us-gov-east-1)."
  default     = "us-gov-east-1"
}

variable "aws_profile" {
  type        = string
  description = "AWS CLI / Identity Center profile used by Terragrunt to deploy this stack."
  default     = ""
}

variable "role_name" {
  type        = string
  description = "IAM role name created in the target account."
  default     = "r-edl-resource-inventory"
}

variable "role_description" {
  type    = string
  default = "Read-only Resource Groups and Resource Groups Tagging API access for EDL inventory"
}

variable "max_session_duration" {
  type    = number
  default = 28800
}

variable "resource_group_account_id" {
  type        = string
  description = "Account ID in the Resource Groups ARN. Empty = this account (screenshot used 053381801543 as an example)."
  default     = ""
}

variable "trusted_principal_arns" {
  type        = list(string)
  description = "Optional extra IAM principal ARNs allowed to assume the role (in addition to Identity Center roles in this account)."
  default     = []
}

variable "trusted_source_account_ids" {
  type        = list(string)
  description = "Optional additional account IDs whose IAM Identity Center roles may assume this role."
  default     = []
}

variable "tags" {
  type    = map(string)
  default = {}
}

variable "verification_dir" {
  type        = string
  description = "Directory for verification.json and verification.md (Terragrunt sets this to the live unit dir)."
  default     = ""
}

variable "fail_if_not_compliant" {
  type        = bool
  description = "If true, terragrunt apply fails when live IAM does not match the screenshot policy."
  default     = false
}
