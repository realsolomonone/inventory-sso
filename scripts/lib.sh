# Shared helpers for inventory-sso operator scripts (bash 3.2 compatible).
# Sourced by scripts/*.sh — not run directly.

if [ -n "${BASH_SOURCE[0]:-}" ]; then
  _LIB_DIR=$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
else
  _LIB_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
fi
ROOT_DIR=$(CDPATH= cd -- "$_LIB_DIR/.." && pwd)

_ini_cache=""

_var_was_set() {
  eval "[ \"\${$1+x}\" = x ]"
}

_save_override() {
  eval "_ov_$1=\${$1-}"
  if _var_was_set "$1"; then
    eval "_set_$1=x"
  else
    eval "_set_$1="
  fi
}

_restore_override() {
  eval "if [ \"\${_set_$1}\" = x ]; then $1=\${_ov_$1}; fi"
}

load_project_env() {
  _save_override ENVIRONMENT
  _save_override ENV_FILE
  _save_override ROLE_NAME
  _save_override ROLE_DESCRIPTION
  _save_override AWS_REGION
  _save_override AWS_PARTITION
  _save_override PROJECT
  _save_override PURPOSE
  _save_override PROJECT_NAME_TAG
  _save_override PROFILE_PREFIX
  _save_override SSO_START_URL
  _save_override EXCLUDE_PROFILES
  _save_override AWS_CONFIG_FILE
  _save_override RESOURCE_GROUP_ACCOUNT_ID
  _save_override TRUSTED_PRINCIPAL_ARNS
  _save_override TRUSTED_SOURCE_ACCOUNT_IDS

  set -a
  # shellcheck disable=SC1091
  [ -f "$ROOT_DIR/config/defaults.env" ] && . "$ROOT_DIR/config/defaults.env"

  _restore_override ENVIRONMENT
  _restore_override ENV_FILE
  ENVIRONMENT="${ENVIRONMENT:-gov-east}"

  if [ -n "${ENV_FILE:-}" ]; then
    if [ ! -f "$ENV_FILE" ]; then
      echo "ENV_FILE not found: $ENV_FILE" >&2
      exit 2
    fi
    # shellcheck disable=SC1090
    . "$ENV_FILE"
  else
    _env_path="$ROOT_DIR/config/envs/${ENVIRONMENT}.env"
    if [ -f "$_env_path" ]; then
      # shellcheck disable=SC1090
      . "$_env_path"
    fi
  fi

  if [ -f "$ROOT_DIR/config/.env" ]; then
    # shellcheck disable=SC1091
    . "$ROOT_DIR/config/.env"
  fi
  set +a

  _restore_override ENVIRONMENT
  _restore_override ENV_FILE
  _restore_override ROLE_NAME
  _restore_override ROLE_DESCRIPTION
  _restore_override AWS_REGION
  _restore_override AWS_PARTITION
  _restore_override PROJECT
  _restore_override PURPOSE
  _restore_override PROJECT_NAME_TAG
  _restore_override PROFILE_PREFIX
  _restore_override SSO_START_URL
  _restore_override EXCLUDE_PROFILES
  _restore_override AWS_CONFIG_FILE
  _restore_override RESOURCE_GROUP_ACCOUNT_ID
  _restore_override TRUSTED_PRINCIPAL_ARNS
  _restore_override TRUSTED_SOURCE_ACCOUNT_IDS

  PROJECT="${PROJECT:-inventory-sso}"
  ENVIRONMENT="${ENVIRONMENT:-gov-east}"
  ROLE_NAME="${ROLE_NAME:-r-edl-resource-inventory}"
  AWS_REGION="${AWS_REGION:-us-gov-east-1}"
  AWS_PARTITION="${AWS_PARTITION:-aws-us-gov}"
  AWS_CONFIG_FILE="${AWS_CONFIG_FILE:-$HOME/.aws/config}"
  PROFILE_PREFIX="${PROFILE_PREFIX:-}"
  SSO_START_URL="${SSO_START_URL:-}"
  EXCLUDE_PROFILES="${EXCLUDE_PROFILES:-}"
  RESOURCE_GROUP_ACCOUNT_ID="${RESOURCE_GROUP_ACCOUNT_ID:-}"
  export PROJECT ENVIRONMENT ROLE_NAME ROLE_DESCRIPTION AWS_REGION AWS_PARTITION
  export PURPOSE PROJECT_NAME_TAG RESOURCE_GROUP_ACCOUNT_ID
  export TRUSTED_PRINCIPAL_ARNS TRUSTED_SOURCE_ACCOUNT_IDS
  export PROFILE_PREFIX SSO_START_URL EXCLUDE_PROFILES AWS_CONFIG_FILE
  export TG_FAIL_IF_NOT_COMPLIANT="${TG_FAIL_IF_NOT_COMPLIANT:-false}"
}

need_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 2
  fi
}

terraform_bin() {
  printf '%s\n' "${TG_TF_PATH:-terraform}"
}

terraform_version_line() {
  "$(terraform_bin)" version 2>/dev/null | head -n1
}

terraform_is_15() {
  _line=$(terraform_version_line)
  _maj=$(printf '%s' "$_line" | sed -n 's/.*v\([0-9][0-9]*\)\.\([0-9][0-9]*\).*/\1/p')
  _min=$(printf '%s' "$_line" | sed -n 's/.*v\([0-9][0-9]*\)\.\([0-9][0-9]*\).*/\2/p')
  [ -n "$_maj" ] || return 1
  [ -n "$_min" ] || return 1
  if [ "$_maj" -gt 1 ]; then
    return 0
  fi
  if [ "$_maj" -eq 1 ] && [ "$_min" -ge 5 ]; then
    return 0
  fi
  return 1
}

require_terraform_15() {
  _bin=$(terraform_bin)
  if ! command -v "$_bin" >/dev/null 2>&1; then
    echo "Terragrunt needs Terraform 1.5+ (check PATH or set TG_TF_PATH). Not found: $_bin" >&2
    exit 2
  fi
  if ! terraform_is_15; then
    echo "Terragrunt is using Terraform $(terraform_version_line)" >&2
    echo "This project requires Terraform >= 1.5.0 (v0.12 cannot parse check/precondition or provider source)." >&2
    echo "Install Terraform 1.5+, put it first on PATH, or: export TG_TF_PATH=/path/to/terraform" >&2
    exit 2
  fi
}

# New Terragrunt CLI (v0.88+): `run-all` is not a command. Use `run --all`.
# Older CLI (e.g. 0.53): `terragrunt run-all plan`.
_tg_new_cli=""

tg_uses_run_flag() {
  if [ -z "$_tg_new_cli" ]; then
    if ! command -v terragrunt >/dev/null 2>&1; then
      _tg_new_cli=1
    elif terragrunt run --help 2>/dev/null | grep -q -- '--all'; then
      _tg_new_cli=1
    else
      _tg_new_cli=0
    fi
  fi
  [ "$_tg_new_cli" = "1" ]
}

tg_all_cmd() {
  if tg_uses_run_flag; then
    printf 'terragrunt run --all %s' "$*"
  else
    printf 'terragrunt run-all %s' "$*"
  fi
}

tg_run_all() {
  if tg_uses_run_flag; then
    echo "Running: terragrunt run --all --non-interactive $*"
    terragrunt run --all --non-interactive "$@"
  else
    echo "Running: terragrunt run-all $* --terragrunt-non-interactive"
    terragrunt run-all "$@" --terragrunt-non-interactive
  fi
}

aws_config_path() {
  printf '%s\n' "${AWS_CONFIG_FILE:-$HOME/.aws/config}"
}

_ini_dump() {
  _cfg=$(aws_config_path)
  if [ ! -f "$_cfg" ]; then
    _ini_cache=""
    return 0
  fi
  _ini_cache=$(awk '
    BEGIN { FS = "=" }
    /^[[:space:]]*#/ { next }
    /^[[:space:]]*;/ { next }
    /^[[:space:]]*$/ { next }
    /^\[/ {
      section = $0
      sub(/^\[/, "", section)
      sub(/\][[:space:]]*$/, "", section)
      next
    }
    {
      line = $0
      eq = index(line, "=")
      if (eq == 0) next
      key = substr(line, 1, eq - 1)
      val = substr(line, eq + 1)
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", key)
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", val)
      print section "\t" key "\t" val
    }
  ' "$_cfg")
}

ini_get() {
  # ini_get "<section>" "<key>"
  printf '%s\n' "$_ini_cache" | awk -F '\t' -v s="$1" -v k="$2" '
    $1 == s && $2 == k { print $3; found=1; exit }
    END { if (!found) exit 0 }
  '
}

list_profile_names() {
  _ini_dump
  printf '%s\n' "$_ini_cache" | awk -F '\t' '
    $1 == "default" { if (!seen["default"]++) print "default" }
    $1 ~ /^profile / {
      name = $1
      sub(/^profile /, "", name)
      if (!seen[name]++) print name
    }
  '
}

profile_section() {
  if [ "$1" = "default" ]; then
    printf '%s\n' "default"
  else
    printf '%s\n' "profile $1"
  fi
}

profile_start_url() {
  _sec=$(profile_section "$1")
  _url=$(ini_get "$_sec" "sso_start_url")
  if [ -n "$_url" ]; then
    printf '%s\n' "$_url"
    return 0
  fi
  _sess=$(ini_get "$_sec" "sso_session")
  if [ -n "$_sess" ]; then
    ini_get "sso-session $_sess" "sso_start_url"
  fi
}

profile_sso_region() {
  _sec=$(profile_section "$1")
  _reg=$(ini_get "$_sec" "sso_region")
  if [ -n "$_reg" ]; then
    printf '%s\n' "$_reg"
    return 0
  fi
  _sess=$(ini_get "$_sec" "sso_session")
  if [ -n "$_sess" ]; then
    ini_get "sso-session $_sess" "sso_region"
  fi
}

is_sso_profile() {
  _url=$(profile_start_url "$1")
  _reg=$(profile_sso_region "$1")
  [ -n "$_url" ] && [ -n "$_reg" ]
}

profile_excluded() {
  _name="$1"
  _old_ifs=$IFS
  IFS=,
  # shellcheck disable=SC2086
  set -- $EXCLUDE_PROFILES
  IFS=$_old_ifs
  for _ex in "$@"; do
    _ex=$(printf '%s' "$_ex" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')
    [ -n "$_ex" ] && [ "$_ex" = "$_name" ] && return 0
  done
  return 1
}

profile_selected() {
  _name="$1"
  if ! is_sso_profile "$_name"; then
    return 1
  fi
  if profile_excluded "$_name"; then
    return 1
  fi
  if [ -n "$PROFILE_PREFIX" ]; then
    case "$_name" in
      "$PROFILE_PREFIX"*) ;;
      *) return 1 ;;
    esac
  fi
  if [ -n "$SSO_START_URL" ]; then
    _url=$(profile_start_url "$_name")
    [ "$_url" = "$SSO_START_URL" ] || return 1
  fi
  return 0
}

list_sso_profiles() {
  list_profile_names | while IFS= read -r _p; do
    [ -n "$_p" ] || continue
    if profile_selected "$_p"; then
      printf '%s\n' "$_p"
    fi
  done
}

profile_region() {
  _sec=$(profile_section "$1")
  _reg=$(ini_get "$_sec" "region")
  if [ -n "$_reg" ]; then
    printf '%s\n' "$_reg"
  else
    printf '%s\n' "$AWS_REGION"
  fi
}

profile_account_id() {
  ini_get "$(profile_section "$1")" "sso_account_id"
}

profile_sso_session() {
  ini_get "$(profile_section "$1")" "sso_session"
}

sso_login_group() {
  _sess=$(profile_sso_session "$1")
  if [ -n "$_sess" ]; then
    printf 'session:%s\n' "$_sess"
    return 0
  fi
  _url=$(profile_start_url "$1")
  printf 'url:%s\n' "$_url"
}

stack_slug() {
  printf '%s' "$1" | sed -e 's/[^A-Za-z0-9._-]/-/g' -e 's/^-*//' -e 's/-*$//'
  printf '\n'
}

print_env_banner() {
  echo "project=$PROJECT  env=$ENVIRONMENT  role=$ROLE_NAME  region=$AWS_REGION"
  echo "aws config=$(aws_config_path)"
}

profile_session_valid() {
  AWS_PROFILE="$1" AWS_REGION="${2:-$AWS_REGION}" aws sts get-caller-identity --profile "$1" >/dev/null 2>&1
}
