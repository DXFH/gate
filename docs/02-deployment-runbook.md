# 02 部署命令与仓库出处

## 代码出处

| 用途 | 仓库 |
|---|---|
| 抓取与工作流 | https://github.com/hezhanleiok/gate |
| 检测 Worker | https://github.com/lsh8848/cm-Workers-CheckSocks5 |
| 链式代理 / edgetunnel | https://github.com/cmliu/edgetunnel |

上游副本放在 `upstream/`（已被 `.gitignore` 排除），Worker 源码固定复制在 `worker/_worker.js`。

## 环境

- WSL，工作目录 `/mnt/h/lab/cloud-iac/gate`（Windows：`H:\lab\cloud-iac\gate`）
- 令牌文件：`~/.cloud-iac.env`（`GITHUB_TOKEN`、`GITHUB_OWNER`）、`~/.cloudflare-deploy.env`（`CLOUDFLARE_API_TOKEN`、`CLOUDFLARE_ACCOUNT_ID`）
- Pulumi 使用本地文件后端：`file://$HOME/.pulumi-gate-state`

## 部署命令

```bash
cd /mnt/h/lab/cloud-iac/gate

# 本地故障注入测试
bash tests/run_tests.sh

# Step 2：Pulumi 部署 Worker + 仓库 + Secret DOMAIN
bash scripts/10-deploy-pulumi.sh

# 推送代码、设置 Workflow Permissions、启用 Pages、触发首次运行
bash scripts/20-publish-repo.sh
```

`10-deploy-pulumi.sh` 内部做的事：

```bash
export PATH="$HOME/.pulumi/bin:$PATH" PULUMI_CONFIG_PASSPHRASE=""
pulumi login "file://$HOME/.pulumi-gate-state"
pulumi stack select dev || pulumi stack init dev
pulumi up --yes --skip-preview --non-interactive
```

读取 Worker 完整检测地址（含 Secret，勿外传）：

```bash
cd pulumi && pulumi stack output checkEndpointSecret --show-secrets
```

## 最终地址

- 仓库：https://github.com/DXFH/gate
- 节点列表：https://dxfh.github.io/gate/nodes.txt
- 状态页：https://dxfh.github.io/gate/