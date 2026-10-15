#!/usr/bin/env bash
# Step 2b: push code to DXFH/gate, enable Pages (Actions source), set Workflow Permissions = read/write, trigger first run.
set -euo pipefail
cd "$(dirname "$0")/.."
source ~/.cloud-iac.env
OWNER=$GITHUB_OWNER; REPO=gate; API=https://api.github.com
H=(-H "Authorization: Bearer $GITHUB_TOKEN" -H "Accept: application/vnd.github+json" -H "X-GitHub-Api-Version: 2022-11-28")

echo "== workflow permissions -> write"
curl -sS -o /dev/null -w "HTTP %{http_code}\n" -X PUT "${H[@]}" $API/repos/$OWNER/$REPO/actions/permissions/workflow \
  -d '{"default_workflow_permissions":"write","can_approve_pull_request_reviews":false}'
curl -sS "${H[@]}" $API/repos/$OWNER/$REPO/actions/permissions/workflow; echo

echo "== git push"
[ -d .git ] || git init -q -b main
git config user.name "$OWNER"; git config user.email "$OWNER@users.noreply.github.com"
git add -A && (git diff --cached --quiet || git commit -q -m "gate: hardened vpngate pipeline, Pulumi IaC, docs")
git remote remove origin 2>/dev/null || true
git remote add origin "https://x-access-token:${GITHUB_TOKEN}@github.com/$OWNER/$REPO.git"
git push -q --force origin main 2>&1 | sed -E 's/(x-access-token:)[^@]+/\1***/'
git remote set-url origin "https://github.com/$OWNER/$REPO.git"

echo "== enable Pages (build_type=workflow)"
code=$(curl -sS -o /tmp/pages.json -w '%{http_code}' -X POST "${H[@]}" $API/repos/$OWNER/$REPO/pages -d '{"build_type":"workflow"}')
echo "POST pages -> $code"; [ "$code" = 409 ] || [ "$code" = 201 ] || cat /tmp/pages.json
curl -sS "${H[@]}" $API/repos/$OWNER/$REPO/pages | python3 -c 'import sys,json;d=json.load(sys.stdin);print({k:d.get(k) for k in ("html_url","build_type","status")})'

echo "== dispatch workflow"
sleep 3
curl -sS -o /dev/null -w "dispatch HTTP %{http_code}\n" -X POST "${H[@]}" $API/repos/$OWNER/$REPO/actions/workflows/vpngate.yml/dispatches -d '{"ref":"main"}'