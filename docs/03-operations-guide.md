# 03 运维指南

## 在 edgetunnel 后台替换节点来源（只需做一次）

1. 打开你的 edgetunnel 管理后台：`https://<你的域名>/admin`。
2. 找到「自定义优选 IP/域名」输入框。
3. 清空原内容，填入：`https://dxfh.github.io/gate/nodes.txt`
4. 保存。之后 Actions 每次更新 Pages，edgetunnel 会自动读取最新列表。
5. Clash Verge 不需要改动，「住宅免费IP组」继续生效。

## 调整定时频率

编辑 `.github/workflows/vpngate.yml`：

```yaml
on:
  schedule:
    - cron: "17 */6 * * *"   # UTC，每 6 小时
```

常用写法：每 3 小时 `17 */3 * * *`；每天一次 `17 2 * * *`。GitHub 的 cron 使用 UTC，高峰期可能延迟几分钟。修改后提交推送即可。

## 手动触发与查看结果

```bash
source ~/.cloud-iac.env
curl -X POST -H "Authorization: Bearer $GITHUB_TOKEN" \
  https://api.github.com/repos/DXFH/gate/actions/workflows/vpngate.yml/dispatches -d '{"ref":"main"}'
```

每次运行的摘要在 Actions 页面的 Summary 中，会显示 `publish` 和可用节点数。

## 可调环境变量（工作流 `env:`）

| 变量 | 默认 | 含义 |
|---|---|---|
| `CHECK_CONCURRENCY` | 32 | 并发检测数 |
| `CHECK_TIMEOUT` | 90 | 单节点检测超时（秒） |
| `RETRY_ATTEMPTS` | 3 | 单次请求重试次数 |
| `BREAKER_THRESHOLD` | 25 | 连续 Worker 异常多少次后熔断 |
| `MIN_SUCCESS_TO_PUBLISH` | 1 | 至少多少个可用节点才发布 |
| `STRICT` | 0 | 设为 1 时失败才以 exit 1 结束 |

## 轮换令牌

令牌只在 WSL 的 env 文件和 Pulumi 状态中。更换后重新执行 `bash scripts/10-deploy-pulumi.sh`，Secret `DOMAIN` 内容不变，无需改动。