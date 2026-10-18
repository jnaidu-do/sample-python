#!/usr/bin/env bash
# Derive a preview-app spec from the base app spec.
# Usage: make-preview-spec.sh <base-spec> <out-spec> <pr-number> <head-branch>
set -euo pipefail

BASE_SPEC="$1"; OUT="$2"; PR="$3"; BRANCH="$4"

BASE_NAME="$(yq '.name' "$BASE_SPEC")"
# App names are limited to 32 chars; keep the PR number intact by trimming the base name.
SUFFIX="-pr-${PR}"
NAME="$(printf '%s' "$BASE_NAME" | cut -c1-$((32 - ${#SUFFIX})))${SUFFIX}"

REPO_SLUG="${GITHUB_REPOSITORY:-$(yq '.services[0].github.repo' "$BASE_SPEC")}"

export NAME PR BRANCH REPO_SLUG
yq '
  .name = strenv(NAME)
  | del(.domains) | del(.alerts) | del(.ingress)
  # Databases: previews ALWAYS get their own throwaway dev database, never an existing cluster.
  | (.databases // []) |= map(.production = false | del(.cluster_name) | del(.db_name) | del(.db_user))
  # Build every component in this repo from the PR branch; we trigger redeploys ourselves.
  | (.services[], .workers[], .jobs[], .static_sites[]) |= (
      select(.github.repo == strenv(REPO_SLUG)).github |= (.branch = strenv(BRANCH) | .deploy_on_push = false)
      // .
    )
  # Let the app show which PR it is.
  | (.services[]) .envs += [{"key": "PREVIEW_PR", "value": strenv(PR), "scope": "RUN_TIME"}, {"key": "PREVIEW_BRANCH", "value": strenv(BRANCH), "scope": "RUN_TIME"}]
' "$BASE_SPEC" > "$OUT"

# Safety net: refuse to proceed if any database could still point at a real cluster.
if [ "$(yq '[(.databases // [])[] | select(.production == true or has("cluster_name"))] | length' "$OUT")" != "0" ]; then
  echo "ERROR: preview spec still references a production database or existing cluster" >&2
  exit 1
fi
echo "$NAME"
