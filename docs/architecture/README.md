# Architecture demo

Present from **[index.html](index.html)** (open in a browser). Three tabs: executive, junior admin, senior engineer.

| Audience | Open | Time |
|----------|------|------|
| Executive | [index.html#exec](index.html#exec) | 5 min |
| Junior admin | [index.html#admin](index.html#admin) | 10 min |
| Senior engineer | [index.html#sme](index.html#sme) | 15 min |

## Diagrams (official AWS icons)

| File | Story |
|------|--------|
| [deploy-architecture.png](deploy-architecture.png) | SSO → Terragrunt → every account → IAM role → Resource Groups (read-only) |
| [verify-architecture.png](verify-architecture.png) | `./scripts/verify.sh` → GetRole → `executive.html` |
| [control-plane.png](control-plane.png) | `~/.aws/config` → generate units → `root.hcl` → terraform-shim → IAM module |

Also: [../edl-inventory-architecture.drawio](../edl-inventory-architecture.drawio) (diagrams.net / Lucidchart), [../EDL-Resource-Inventory-Terragrunt-Workflow.pptx](../EDL-Resource-Inventory-Terragrunt-Workflow.pptx).

## Written briefs

- [executive.md](executive.md)
- [junior-admin.md](junior-admin.md)
- [senior-engineer.md](senior-engineer.md)
