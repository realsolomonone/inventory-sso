# Senior engineer SME

## Split of duties

| Piece | Path | Rule |
|-------|------|------|
| Operator | Terragrunt `run --all` | Terraform CLI is not the operator path |
| Control plane | `infra/live/root.hcl` | generate provider, merge inputs, TF ≥ 1.5 shim |
| Live units | `infra/live/accounts/<profile>/` | generated, gitignored, one SSO profile each |
| Create module | `infra/modules/r-edl-resource-inventory` | role + inline policy + check/precondition |
| TG verify | `infra/modules/verify-role` | data-only, no IAM writes |
| Python verify | `src/verifier.py` + `scripts/verify.sh` | GetRole / GetRolePolicy → HTML |

## IAM

- Trust: `AllowSSOAssume`, `ArnLike` SSO reserved roles in-account (plus optional extra ARNs).
- Policy SIDs: `ViewSpecificResourceGroup`, `TaggingReadOnly` (same as the original screenshot; account ID is parameterized).

## Python checks (`evaluate_role`)

1. Role exists  
2. Trust has `sso.amazonaws.com` + `sts:AssumeRole`  
3. View SID covers Get/List/Search  
4. Resource Groups ARN for this account  
5. Tagging SID on `*`  
6. Optional `tag:GetTagKeys` probe  

Skipped SSO sessions become `denied` rows; HTML is still written. Overall status: pass / partial / fail.

## Do not

- `include.expose` (breaks new Terragrunt `run --all`)
- `retryable_errors` on this CLI
- `--all` from `infra/live` (picks up extra stacks)
- Port the IAM module to Terraform 0.12
