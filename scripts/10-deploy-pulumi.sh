#!/usr/bin/env bash
# Step 2: Pulumi -> Cloudflare Worker (check-sstp) + GitHub repo + Actions secret DOMAIN
set -euo pipefail
cd "$(dirname "$0")/../pulumi"
source ~/.cloud-iac.env            # GITHUB_TOKEN, GITHUB_OWNER (and lab CF token, overridden below)
source ~/.cloudflare-deploy.env    # CLOUDFLARE_API_TOKEN (Workers) + CLOUDFLARE_ACCOUNT_ID
export PATH="$HOME/.pulumi/bin:$PATH" PULUMI_CONFIG_PASSPHRASE=""
mkdir -p "$HOME/.pulumi-gate-state"
pulumi login "file://$HOME/.pulumi-gate-state" >/dev/null
pulumi stack select dev 2>/dev/null || pulumi stack init dev
pulumi up --yes --skip-preview --non-interactive 2>&1 | sed -E 's/(github_pat_|ghp_|cfut_)[A-Za-z0-9_]+/\1***/g'
echo "--- outputs (secrets hidden)"
pulumi stack output