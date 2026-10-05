"""HTML reports for the resource inventory."""

from __future__ import annotations

import html
from pathlib import Path

from .models import Inventory, VerifyReport
from .reports import stamp

SHARED_STYLES = """
:root {
  --bg: #eef2f7;
  --card: #ffffff;
  --text: #111827;
  --muted: #6b7280;
  --line: #e5e7eb;
  --green-bg: #dcfce7;
  --green-text: #166534;
  --yellow-bg: #fef9c3;
  --yellow-text: #854d0e;
  --red-bg: #fee2e2;
  --red-text: #991b1b;
  --accent: #1e3a8a;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.5;
}
.wrap { max-width: 1280px; margin: 0 auto; padding: 28px 20px 56px; }
.hero { background: #1e3a8a; color: #fff; border-radius: 12px; padding: 28px 32px; margin-bottom: 24px; }
.hero h1 { margin: 0 0 6px; font-size: 1.7rem; }
.hero .subtitle { color: #dbeafe; margin: 0; }
.hero-nav { margin-top: 16px; display: flex; flex-wrap: wrap; gap: 10px; }
.hero-nav a { color: #fff; text-decoration: none; padding: 8px 14px; border-radius: 8px; font-weight: 600; border: 1px solid rgba(255,255,255,0.35); }
.cards { display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: 16px; margin-bottom: 24px; }
.card, .panel { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 20px; margin-bottom: 20px; }
.card .label, .panel h2 { color: var(--muted); font-size: 0.82rem; font-weight: 700; text-transform: uppercase; margin: 0 0 8px; }
.card .value { font-size: 1.7rem; font-weight: 800; }
.table-wrap { overflow-x: auto; }
table.data { width: 100%; border-collapse: collapse; font-size: 0.86rem; }
table.data th, table.data td { padding: 10px 12px; border-bottom: 1px solid var(--line); text-align: left; vertical-align: top; }
table.data th { background: #f8fafc; color: var(--muted); font-size: 0.72rem; text-transform: uppercase; }
.badge { display: inline-block; padding: 3px 10px; border-radius: 999px; font-size: 0.74rem; font-weight: 700; }
.badge-pass, .badge-complete, .badge-ok { background: var(--green-bg); color: var(--green-text); }
.badge-fail, .badge-untagged, .badge-denied, .badge-error, .badge-missing { background: var(--red-bg); color: var(--red-text); }
.badge-partial, .badge-invalid { background: var(--yellow-bg); color: var(--yellow-text); }
.row-fail { background: #fef2f2; }
.row-pass { background: #f0fdf4; }
.row-missing { background: #fff7ed; }
.footer { color: var(--muted); font-size: 0.82rem; }
.checks { font-size: 0.82rem; color: var(--muted); margin: 0; padding-left: 18px; }
.mono { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 0.8rem; word-break: break-all; }
.banner { border-radius: 12px; padding: 18px 24px; margin-bottom: 20px; font-size: 1.35rem; font-weight: 800; letter-spacing: 0.02em; }
.banner-pass { background: var(--green-bg); color: var(--green-text); }
.banner-partial { background: var(--yellow-bg); color: var(--yellow-text); }
.banner-fail, .banner-empty { background: var(--red-bg); color: var(--red-text); }
.filter { width: 100%; padding: 10px 12px; border: 1px solid var(--line); border-radius: 8px; font-size: 0.95rem; margin: 0 0 12px; }
details.acct { background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 4px 16px 12px; margin-bottom: 12px; }
details.acct summary { cursor: pointer; font-weight: 700; padding: 12px 0; }

"""


def _esc(value: object) -> str:
    return html.escape("" if value is None else str(value))


def _badge(status: str) -> str:
    return f'<span class="badge badge-{_esc(status)}">{_esc(status)}</span>'


def write_html_reports(inventory: Inventory, output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    tag = stamp(inventory)
    reports = dict(inventory.reports)
    index = output_dir / f"inventory-index-{tag}.html"
    executive = output_dir / f"executive-summary-{tag}.html"
    reports["index_html"] = str(index)
    reports["executive_html"] = str(executive)
    subtitle = f"{inventory.ticket} · generated {inventory.generated_at}"
    index.write_text(_page("EDL resource inventory", subtitle, reports, _index_body(inventory, reports)), encoding="utf-8")
    executive.write_text(_page("Executive summary", subtitle, reports, _executive_body(inventory)), encoding="utf-8")
    return reports


def _nav(reports: dict[str, str]) -> str:
    links = []
    mapping = (
        ("index_html", "Index"),
        ("executive_html", "Executive"),
        ("verify_html", "Role verify"),
        ("verify_index_html", "Verify index"),
        ("inventory_csv", "Inventory CSV"),
        ("verify_accounts_csv", "Verify CSV"),
        ("json", "JSON"),
        ("verify_json", "Verify JSON"),
    )
    for key, label in mapping:
        path = reports.get(key)
        if path:
            links.append(f'<a href="{_esc(Path(path).name)}">{_esc(label)}</a>')
    return "".join(links)


def _page(title: str, subtitle: str, reports: dict[str, str], body: str, extra_script: str = "") -> str:
    script = f"<script>{extra_script}</script>" if extra_script else ""
    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><title>{_esc(title)}</title>
<style>{SHARED_STYLES}</style></head>
<body><div class="wrap">
  <div class="hero"><h1>{_esc(title)}</h1><p class="subtitle">{_esc(subtitle)}</p>
  <div class="hero-nav">{_nav(reports)}</div></div>
  {body}
  <p class="footer">Role r-edl-resource-inventory · Resource Groups Tagging API · SSO profiles from ~/.aws/config</p>
</div>{script}</body></html>
"""


def _kpis(inventory: Inventory) -> str:
    return f"""
    <div class="cards">
      <div class="card"><div class="label">Tagged resources</div><div class="value">{inventory.resources_total}</div></div>
      <div class="card"><div class="label">Tag completeness</div><div class="value">{inventory.completeness_pct}%</div></div>
      <div class="card"><div class="label">Need fixes</div><div class="value">{inventory.resources_missing}</div></div>
      <div class="card"><div class="label">Accounts</div><div class="value">{len(inventory.accounts)}</div></div>
    </div>
    """


def _accounts_table(inventory: Inventory) -> str:
    rows = []
    for account in inventory.accounts:
        rows.append(
            "<tr>"
            f"<td>{_esc(account.profile)}</td>"
            f"<td>{_esc(account.account_id)}</td>"
            f"<td>{_badge(account.status.value)}</td>"
            f"<td>{account.resources_total}</td>"
            f"<td>{account.resources_complete}</td>"
            f"<td>{account.resources_needs_fix}</td>"
            f"<td>{account.groups_total}</td>"
            f"<td>{_esc(account.message)}</td>"
            "</tr>"
        )
    body = "".join(rows) or '<tr><td colspan="8">No accounts scanned.</td></tr>'
    return f"""
    <div class="panel"><h2>Accounts</h2>
    <div class="table-wrap"><table class="data">
      <thead><tr><th>Profile</th><th>Account</th><th>Status</th><th>Resources</th><th>Complete</th><th>Need fix</th><th>Groups</th><th>Notes</th></tr></thead>
      <tbody>{body}</tbody>
    </table></div></div>
    """


def _resources_table(inventory: Inventory, limit: int = 80) -> str:
    tagged = [row for row in inventory.records if row.kind == "resource"][:limit]
    rows = []
    for record in tagged:
        missing = ", ".join(record.missing_tags) if record.missing_tags else "—"
        rows.append(
            f"<tr class='row-{_esc(record.health.value)}'>"
            f"<td>{_esc(record.account_name)}</td>"
            f"<td>{_esc(record.service)}</td>"
            f"<td class='mono'>{_esc(record.resource_arn)}</td>"
            f"<td>{_badge(record.health.value)}</td>"
            f"<td>{record.completeness_pct:.0f}%</td>"
            f"<td>{_esc(missing)}</td>"
            "</tr>"
        )
    extra = ""
    total = sum(1 for row in inventory.records if row.kind == "resource")
    if total > limit:
        extra = f"<p class='footer'>Showing {limit} of {total} tagged resources. Full list is in the CSV.</p>"
    body = "".join(rows) or "<tr><td colspan='6'>No tagged resources returned.</td></tr>"
    return f"""
    <div class="panel"><h2>Tagged resources</h2>
    <div class="table-wrap"><table class="data">
      <thead><tr><th>Account</th><th>Service</th><th>ARN</th><th>Tags</th><th>%</th><th>Missing</th></tr></thead>
      <tbody>{body}</tbody>
    </table></div>{extra}</div>
    """


def _index_body(inventory: Inventory, reports: dict[str, str]) -> str:
    files = "".join(
        f"<tr><td>{_esc(key)}</td><td><a href='{_esc(Path(path).name)}'>{_esc(path)}</a></td></tr>"
        for key, path in sorted(reports.items())
        if path
    )
    return f"{_kpis(inventory)}{_accounts_table(inventory)}{_resources_table(inventory)}<div class='panel'><h2>Deliverables</h2><div class='table-wrap'><table class='data'><tbody>{files}</tbody></table></div></div>"


def _executive_body(inventory: Inventory) -> str:
    narrative = "".join(f"<li>{_esc(line)}</li>" for line in inventory.narrative)
    return f"{_kpis(inventory)}<div class='panel'><h2>Documented results</h2><ol>{narrative}</ol></div>{_accounts_table(inventory)}{_resources_table(inventory, limit=25)}"


def write_verify_html_reports(report: VerifyReport, output_dir: Path) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    tag = (
        report.generated_at.replace(":", "")
        .replace(" ", "-")
        .replace("UTC", "")
        .replace("--", "-")
        .strip("-")
    )
    reports = dict(report.reports)
    latest = output_dir / "role-verify.html"
    archive = output_dir / f"role-verify-{tag}.html"
    reports["verify_html"] = str(latest)
    reports["verify_html_archive"] = str(archive)
    subtitle = f"{report.ticket} · role {report.role_name} · {report.generated_at}"
    page = _page(
        f"Verify {report.role_name}",
        subtitle,
        reports,
        _verify_report_body(report, reports),
        extra_script=_VERIFY_FILTER_JS,
    )
    latest.write_text(page, encoding="utf-8")
    archive.write_text(page, encoding="utf-8")
    return reports


def _verify_kpis(report: VerifyReport) -> str:
    return f"""
    <div class="cards">
      <div class="card"><div class="label">Accounts</div><div class="value">{len(report.accounts)}</div></div>
      <div class="card"><div class="label">Pass</div><div class="value">{report.passed_count}</div></div>
      <div class="card"><div class="label">Fail / missing</div><div class="value">{report.failed_count + report.missing_count}</div></div>
      <div class="card"><div class="label">Denied / error</div><div class="value">{report.blocked_count}</div></div>
    </div>
    """


def _verify_account_rows(report: VerifyReport) -> str:
    rows = []
    for account in report.accounts:
        rows.append(
            f"<tr class='row-{_esc(account.status)}'>"
            f"<td>{_esc(account.profile)}</td>"
            f"<td>{_esc(account.account_id)}</td>"
            f"<td>{_badge(account.status)}</td>"
            f"<td class='mono'>{_esc(account.role_arn or '—')}</td>"
            f"<td>{account.checks_passed}/{account.checks_passed + account.checks_failed}</td>"
            f"<td>{_esc(account.created or '—')}</td>"
            f"<td>{_esc(account.message or account.probe or '—')}</td>"
            "</tr>"
        )
    body = "".join(rows) or "<tr><td colspan='7'>No accounts verified.</td></tr>"
    return f"""
    <div class="table-wrap"><table class="data" id="acct-table">
      <thead><tr><th>Profile</th><th>Account</th><th>Overall</th><th>Role ARN</th><th>Checks</th><th>Created</th><th>Notes</th></tr></thead>
      <tbody>{body}</tbody>
    </table></div>
    """


def _verify_banner(report: VerifyReport) -> str:
    status = report.overall_status
    labels = {
        "pass": "ALL ACCOUNTS PASS — role created and policy matches",
        "partial": "PARTIAL — some accounts passed; others failed or missing",
        "fail": "FAIL — role not created or policy does not match",
        "empty": "NO ACCOUNTS — login SSO profiles first",
    }
    return f'<div class="banner banner-{_esc(status)}">{_esc(labels.get(status, status.upper()))}</div>'


def _verify_check_table(account) -> str:
    checks = []
    for item in account.checks:
        result = "pass" if item.passed else "fail"
        checks.append(
            f"<tr class='row-{result}'>"
            f"<td>{_esc(item.name)}</td>"
            f"<td>{_badge(result)}</td>"
            f"<td>{_esc(item.expected)}</td>"
            f"<td class='mono'>{_esc(item.found)}</td>"
            f"<td>{_esc(item.detail)}</td>"
            "</tr>"
        )
    table = "".join(checks) or "<tr><td colspan='5'>No checks (dry-run or STS failure).</td></tr>"
    return (
        "<div class='table-wrap'><table class='data'>"
        "<thead><tr><th>Check</th><th>Result</th><th>Expected</th><th>Found</th><th>Detail</th></tr></thead>"
        f"<tbody>{table}</tbody></table></div>"
    )


def _verify_report_body(report: VerifyReport, reports: dict[str, str]) -> str:
    narrative = "".join(f"<li>{_esc(line)}</li>" for line in report.narrative)
    files = "".join(
        f"<tr><td>{_esc(key)}</td><td><a href='{_esc(Path(path).name)}'>{_esc(path)}</a></td></tr>"
        for key, path in sorted(reports.items())
        if path
    )
    details = []
    for account in report.accounts:
        details.append(
            f"<details class='acct' data-filter='{_esc(account.profile)} {_esc(account.account_id)} {_esc(account.status)}' open>"
            f"<summary>{_esc(account.profile)} · {_esc(account.account_id or '—')} · {_badge(account.status)}</summary>"
            f"<p class='mono'>{_esc(account.role_arn or account.message or '—')}</p>"
            f"{_verify_check_table(account)}</details>"
        )
    return (
        f"{_verify_banner(report)}"
        f"{_verify_kpis(report)}"
        f"<div class='panel'><h2>Summary</h2><ol>{narrative}</ol></div>"
        f"<div class='panel'><h2>Role creation by account</h2>"
        f"<input class='filter' id='acct-filter' type='search' placeholder='Filter profile or account…'>"
        f"{_verify_account_rows(report)}</div>"
        f"{''.join(details)}"
        f"<div class='panel'><h2>Files</h2><div class='table-wrap'><table class='data'><tbody>{files}</tbody></table></div></div>"
    )


_VERIFY_FILTER_JS = """
(function () {
  var input = document.getElementById('acct-filter');
  if (!input) return;
  input.addEventListener('input', function () {
    var q = (input.value || '').toLowerCase();
    document.querySelectorAll('#acct-table tbody tr').forEach(function (row) {
      row.style.display = !q || row.textContent.toLowerCase().indexOf(q) !== -1 ? '' : 'none';
    });
    document.querySelectorAll('details.acct').forEach(function (el) {
      var hay = (el.getAttribute('data-filter') || '').toLowerCase();
      el.style.display = !q || hay.indexOf(q) !== -1 ? '' : 'none';
    });
  });
})();
"""
