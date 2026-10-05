#!/usr/bin/env bash
# Authenticate IAM Identity Center profiles in ~/.aws/config (no Python).
# Default: one `aws sso login` per SSO session / start URL, then every matching
# profile can use the cached token.
#
#   ./scripts/sso-login.sh --all
#   ./scripts/sso-login.sh --only-expired
#   ./scripts/sso-login.sh --profiles edl-addcp-dev-ew
#   ENVIRONMENT=commercial ./scripts/sso-login.sh --all
#   ./scripts/sso-login.sh --all --dry-run

set -euo pipefail
. "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)/lib.sh"
load_project_env

usage() {
  cat <<'EOF'
Usage: ./scripts/sso-login.sh [--all] [--only-expired] [--profiles NAME ...] [--per-profile] [--dry-run]

  --all            Login every matching SSO profile in ~/.aws/config
  --only-expired   Skip profiles whose STS session is already valid
  --profiles NAME  Limit to these profile names
  --per-profile    Run aws sso login once per profile (default: once per SSO session)
  --dry-run        Print commands; do not login

Filters (from config/envs/*.env): PROFILE_PREFIX, SSO_START_URL, EXCLUDE_PROFILES
EOF
}

ALL=0
ONLY_EXPIRED=0
PER_PROFILE=0
DRY_RUN=0
PROFILES=""

while [ $# -gt 0 ]; do
  case "$1" in
    -h|--help) usage; exit 0 ;;
    --all) ALL=1; shift ;;
    --only-expired) ONLY_EXPIRED=1; shift ;;
    --per-profile) PER_PROFILE=1; shift ;;
    --dry-run) DRY_RUN=1; shift ;;
    --profiles)
      shift
      while [ $# -gt 0 ]; do
        case "$1" in
          --*) break ;;
          *) PROFILES="${PROFILES:+$PROFILES }$1"; shift ;;
        esac
      done
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [ "$ALL" -eq 0 ] && [ "$ONLY_EXPIRED" -eq 0 ] && [ -z "$PROFILES" ]; then
  usage >&2
  echo "Specify --all, --only-expired, and/or --profiles NAME …" >&2
  exit 2
fi

need_cmd aws
print_env_banner
echo

if [ ! -f "$(aws_config_path)" ]; then
  echo "No AWS config at $(aws_config_path)" >&2
  exit 2
fi

_ini_dump

selected=""
if [ -n "$PROFILES" ]; then
  for _p in $PROFILES; do
    selected="${selected}${_p}
"
  done
else
  selected=$(list_sso_profiles)
fi

if [ -z "$(printf '%s' "$selected" | sed '/^$/d')" ]; then
  echo "No SSO profiles selected. Add Identity Center profiles to $(aws_config_path)"
  echo "or set PROFILE_PREFIX / SSO_START_URL in the env file."
  exit 2
fi

attempted=0
failed=0
skipped=0
ok=0
logged_groups=""

login_one() {
  _profile="$1"
  attempted=$((attempted + 1))
  if [ "$DRY_RUN" -eq 1 ]; then
    if [ "$_profile" = "default" ]; then
      echo "  [DRY] aws sso login"
    else
      echo "  [DRY] aws sso login --profile $_profile"
    fi
    ok=$((ok + 1))
    return 0
  fi
  if [ "$_profile" = "default" ]; then
    echo "  [LOGIN] aws sso login"
    set +e
    aws sso login
    rc=$?
    set -e
  else
    echo "  [LOGIN] aws sso login --profile $_profile"
    set +e
    aws sso login --profile "$_profile"
    rc=$?
    set -e
  fi
  if [ "$rc" -eq 0 ]; then
    echo "  [OK] $_profile"
    ok=$((ok + 1))
    return 0
  fi
  echo "  [FAIL] $_profile (aws sso login exit $rc)"
  failed=$((failed + 1))
  return 1
}

already_logged() {
  case " $logged_groups " in
    *" $1 "*) return 0 ;;
    *) return 1 ;;
  esac
}

OLDIFS=$IFS
IFS='
'
# shellcheck disable=SC2086
set -- $selected
IFS=$OLDIFS

for _p in "$@"; do
  [ -n "$_p" ] || continue
  if [ -n "$PROFILES" ] && ! is_sso_profile "$_p"; then
    echo "  [SKIP] $_p — not an SSO profile"
    skipped=$((skipped + 1))
    continue
  fi
  if profile_excluded "$_p"; then
    echo "  [SKIP] $_p — excluded"
    skipped=$((skipped + 1))
    continue
  fi
  if [ "$ONLY_EXPIRED" -eq 1 ]; then
    if profile_session_valid "$_p"; then
      echo "  [SKIP] $_p — session already valid"
      skipped=$((skipped + 1))
      continue
    fi
  fi

  if [ "$PER_PROFILE" -eq 1 ]; then
    login_one "$_p" || true
    continue
  fi

  _group=$(sso_login_group "$_p")
  if already_logged "$_group"; then
    echo "  [SKIP] $_p — same SSO session already logged in"
    skipped=$((skipped + 1))
    continue
  fi
  if login_one "$_p"; then
    logged_groups="${logged_groups} ${_group}"
  fi
done

echo "--------------------------------------------------"
echo "  SSO login attempted: $attempted"
echo "  Skipped:             $skipped"
echo "  Failed:              $failed"
echo
if [ "$failed" -gt 0 ]; then
  echo "Next: aws sso login --profile PROFILE-NAME"
  exit 1
fi
echo "Next: ./scripts/sso-profiles.sh --check"
echo "Then: ./scripts/stacks-generate.sh"
echo "Then: cd infra/live/accounts && terragrunt run --all apply"
exit 0
