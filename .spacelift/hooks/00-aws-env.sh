#!/usr/bin/env bash
set -euo pipefail
echo "[00-aws-env] Neutralizing AWS profiles & verifying credentials..."
export AWS_SDK_LOAD_CONFIG=0
unset AWS_PROFILE || true
unset AWS_DEFAULT_PROFILE || true
echo "[00-aws-env] AWS_REGION=${AWS_REGION:-}"
echo "[00-aws-env] AWS_ACCESS_KEY_ID is ${AWS_ACCESS_KEY_ID:+present}"
echo "[00-aws-env] AWS_SESSION_TOKEN is ${AWS_SESSION_TOKEN:+present}"
aws sts get-caller-identity >/dev/null
echo "[00-aws-env] STS identity OK. Continuing…"
