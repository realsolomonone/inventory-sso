# Executive brief

**Outcome:** IAM role `r-edl-resource-inventory` in every Identity Center account. Read-only Resource Groups and tags. No write access.

**How:** Terragrunt applies one stack per account. Python proves the role exists and prints `reports/executive.html`.

**Trust:** only IAM Identity Center roles (`aws-reserved/sso.amazonaws.com/*`).

**Ask:** How many accounts **PASS** vs **MISSING** / **DENIED**? Open `reports/executive.html`.
