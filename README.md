# EDL resource inventory

Terragrunt creates IAM role **r-edl-resource-inventory** in every IAM Identity Center account. Python verifies it and writes an executive HTML report.

Do not run `terraform` against this repo. On iebcloud, PATH terraform is often **v0.12.31** — Terragrunt uses `scripts/terraform-shim` (needs Terraform **1.5+**).

```bash
module load terraform/1.5   # if terraform version is 0.12
export TG_TF_PATH=$(command -v terraform)
```

---

## Deploy (Terragrunt)

```bash
cd ~/workspace/inventory-sso
./scripts/doctor.sh
./scripts/sso-login.sh --all
./scripts/sso-profiles.sh --check
./scripts/stacks-generate.sh
cd infra/live/accounts && terragrunt run --all plan
terragrunt run --all apply
```

One account: `cd infra/live/accounts/<profile> && terragrunt apply`  
Destroy: `cd infra/live/accounts && terragrunt run --all destroy`  
Use `terragrunt run --all`, not `run-all`.

---

## Verify (Python → executive HTML)

One command. Creates `.venv`, installs deps, checks the role in every SSO account, opens the report.

```bash
./scripts/verify.sh
```

| File | Audience |
|------|----------|
| `reports/executive.html` | Executives — pass / fail / missing by account |
| `reports/role-verify.html` | Engineers — per-check detail |

```bash
./scripts/verify.sh --profiles YOUR_PROFILE
./scripts/verify.sh --no-probe
```

Manual equivalent:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
./scripts/sso-login.sh --all
python edl_resource_inventory.py verify --open
```

---

## Architecture demo (executive / junior admin / SME)

Open **[docs/architecture/index.html](docs/architecture/index.html)** in a browser.

`docs/architecture/` — diagrams, briefs, and the live demo tabs.  
PowerPoint: `docs/EDL-Resource-Inventory-Terragrunt-Workflow.pptx`

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `unknown command: "run-all"` | `terragrunt run --all plan` |
| Terraform `0.12.31` | `module load terraform/1.5` then `export TG_TF_PATH=$(command -v terraform)` |
| Verify SKIP / no HTML | `./scripts/sso-login.sh --all` then `./scripts/verify.sh` |
| Role **missing** | Apply first: `cd infra/live/accounts && terragrunt run --all apply` |
| `ModuleNotFoundError` | Use `./scripts/verify.sh` (it builds `.venv`) |
| extra stacks | Run `--all` from `infra/live/accounts`, not `infra/live` |
