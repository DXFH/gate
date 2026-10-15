import * as pulumi from "@pulumi/pulumi";
import * as cloudflare from "@pulumi/cloudflare";
import * as github from "@pulumi/github";
import * as fs from "fs";
import * as path from "path";

// Credentials come from the environment (never from code / Pulumi config):
//   CLOUDFLARE_API_TOKEN, CLOUDFLARE_ACCOUNT_ID, GITHUB_TOKEN, GITHUB_OWNER
const cfg = new pulumi.Config();
const accountId = process.env.CLOUDFLARE_ACCOUNT_ID!;
const cfToken = process.env.CLOUDFLARE_API_TOKEN!;
const owner = process.env.GITHUB_OWNER!;
const workerName = cfg.get("workerName") ?? "check-sstp";
const repoName = cfg.get("repoName") ?? "gate";

// 1) Cloudflare: CheckSocks5 Worker (source pinned in ../worker/_worker.js from lsh8848/cm-Workers-CheckSocks5)
const workerSource = fs.readFileSync(path.join(__dirname, "..", "worker", "_worker.js"), "utf-8").replace(/^\uFEFF/, "");
const worker = new cloudflare.WorkersScript("check-worker", {
    accountId,
    scriptName: workerName,
    content: workerSource,
    mainModule: "_worker.js",
    compatibilityDate: "2026-05-01",
});
// Expose on <worker>.<account-subdomain>.workers.dev
const subdomainEnabled = new cloudflare.WorkersScriptSubdomain("check-worker-subdomain", {
    accountId,
    scriptName: worker.scriptName,
    enabled: true,
});

// Account-level workers.dev subdomain (already registered on the account) -> full endpoint
const accountSubdomain = pulumi.output(
    fetch(`https://api.cloudflare.com/client/v4/accounts/${accountId}/workers/subdomain`, {
        headers: { Authorization: `Bearer ${cfToken}` },
    }).then(r => r.json()).then((j: any) => {
        if (!j.success) throw new Error("cannot read workers.dev subdomain: " + JSON.stringify(j.errors));
        return j.result.subdomain as string;
    }),
);
const checkEndpoint = pulumi.interpolate`https://${worker.scriptName}.${accountSubdomain}.workers.dev/check?sstp=vpn:vpn@`;

// 2) GitHub: public repo (free Pages needs public) + Actions secret DOMAIN
const repo = new github.Repository("gate-repo", {
    name: repoName,
    description: "VPN Gate SSTP node checker -> GitHub Pages nodes.txt (for edgetunnel custom preferred IP)",
    visibility: "public",
    autoInit: true,            // main branch must exist before Pages / pushes
    hasIssues: false,
    hasProjects: false,
    hasWiki: false,
    deleteBranchOnMerge: true,
}, { protect: false });

const domainSecret = new github.ActionsSecret("domain-secret", {
    repository: repo.name,
    secretName: "DOMAIN",
    plaintextValue: pulumi.secret(checkEndpoint),
});

export const workerScript = worker.scriptName;
export const repoUrl = repo.htmlUrl;
export const pagesNodesUrl = pulumi.interpolate`https://${owner}.github.io/${repoName}/nodes.txt`;
export const domainSecretName = domainSecret.secretName;
export const checkEndpointSecret = pulumi.secret(checkEndpoint); // `pulumi stack output --show-secrets` to read
export const subdomainOn = subdomainEnabled.enabled;