#!/usr/bin/env bash
# List (and optionally STS-check) IAM Identity Center profiles.

set -euo pipefail
. "$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)/lib.sh"
load_project_env

CHECK=0
JSON=0
SSO_ONLY=0

while [ $# -gt 0 ]; do
  case "$1" in
    --check) CHECK=1; shift ;;
    --json) JSON=1; shift ;;
    --sso-only) SSO_ONLY=1; shift ;;
    -h|--help)
      echo "Usage: ./scripts/sso-profiles.sh [--check] [--json] [--sso-only]"
      exit 0
      ;;
    *) echo "Unknown argument: $1" >&2; exit 2 ;;
  esac
done

if [ ! -f "$(aws_config_path)" ]; then
  echo "No AWS config at $(aws_config_path)" >&2
  exit 2
fi

_ini_dump
print_env_banner
echo

invalid=0
count=0

if [ "$JSON" -eq 1 ]; then
  echo '['
fi

first=1
OLDIFS=$IFS
IFS='
'
# shellcheck disable=SC2046
set -- $(list_profile_names)
IFS=$OLDIFS

for _p in "$@"; do
  [ -n "$_p" ] || continue
  _sso=0
  is_sso_profile "$_p" && _sso=1
  if [ "$SSO_ONLY" -eq 1 ] && [ "$_sso" -eq 0 ]; then
    continue
  fi
  _acct=$(profile_account_id "$_p")
  _reg=$(profile_region "$_p")
  _kind=static
  [ "$_sso" -eq 1 ] && _kind=SSO
  _status=""
  _msg=""
  if [ "$CHECK" -eq 1 ]; then
    if profile_session_valid "$_p" "$_reg"; then
      _status=OK
      _msg="sts ok"
    else
      _status=INVALID
      _msg="sts failed"
      invalid=$((invalid + 1))
    fi
  fi
  count=$((count + 1))
  if [ "$JSON" -eq 1 ]; then
    [ "$first" -eq 1 ] || printf ',\n'
    first=0
    printf '  {"profile":"%s","sso":%s,"account_id":"%s","region":"%s","valid":%s}' \
      "$_p" "$([ "$_sso" -eq 1 ] && echo true || echo false)" "$_acct" "$_reg" \
      "$([ "$_status" = OK ] && echo true || { [ "$CHECK" -eq 1 ] && echo false || echo null; })"
  elif [ "$CHECK" -eq 1 ]; then
    echo "  [${_status}] ${_p} (${_kind}, ${_acct:-—}) — ${_msg}"
  else
    echo "  ${_p}  (${_kind}, ${_acct:-—}, ${_reg})"
  fi
done

if [ "$JSON" -eq 1 ]; then
  echo
  echo ']'
fi

if [ "$count" -eq 0 ]; then
  echo "No profiles found in $(aws_config_path)"
  exit 2
fi

if [ "$CHECK" -eq 1 ] && [ "$invalid" -gt 0 ]; then
  echo
  echo "$invalid profile(s) need attention."
  echo "Refresh: ./scripts/sso-login.sh --all"
  echo "Single:  aws sso login --profile PROFILE-NAME"
  exit 1
fi

exit 0
