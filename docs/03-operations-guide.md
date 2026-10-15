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
    - cron: "17 */2 * * *"   # UTC，每 2 小时（当前默认）
```

**推荐每 1 到 2 小时一次。** 低于 30 分钟没有必要：VPN Gate 对同一 IP 的抓取有频率限制，Worker 的免费额度也会被白白消耗（每轮约检测 90 个节点 = 约 90 次请求；每 2 小时一轮，一天约 1000 次，远低于免费版每日 10 万次）。

| 频率 | cron |
|---|---|
| 每 30 分钟（不推荐） | `*/30 * * * *` |
| 每 1 小时 | `17 * * * *` |
| 每 2 小时（默认） | `17 */2 * * *` |
| 每 4 小时 | `17 */4 * * *` |
| 每 12 小时 | `17 */12 * * *` |
| 每天一次 | `17 2 * * *` |

分钟数故意用 17 而不是 0，避开整点的排队高峰。cron 使用 UTC。

### 定时任务不自动跑了怎么办

- 定时任务只在**默认分支**上生效，工作流文件必须在 `main` 上。
- 公开仓库 **60 天没有任何仓库活动**，GitHub 会自动停用定时工作流。到 Actions 页面点 Enable workflow 即可恢复，或隔段时间推送一次提交。
- 新建仓库的第一次定时触发可能延迟，先用 Run workflow 手动跑一次。
- 公开仓库使用标准运行器是免费的，不受「每月 2000 分钟」限制（那是私有仓库的额度）。

## 优选域名与优选 API（可选，用仓库变量，不用改代码）

仓库 Settings → Secrets and variables → Actions → **Variables** 页签：

| 变量 | 作用 | 示例 |
|---|---|---|
| `EDGE_HOSTS` | 静态优选域名池，逗号分隔，每个必须带端口 | `saas.sin.fan:443,cdn.204910.best:443` |
| `OPTIMAL_API` | 优选 API，可填多个，逗号分隔 | 见下表 |

留空就使用代码内置的默认值。

| 线路 | OPTIMAL_API |
|---|---|
| 电信（默认） | `https://cf.090227.xyz/ct?ips=6&port=443` |
| 联通 | `https://cf.090227.xyz/cu?port=443` |
| 移动 | `https://cf.090227.xyz/cmcc?ips=8&port=443` |
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
## Clash Verge 侧：刷新订阅与测试

**原则：Clash Verge 里不需要替换任何配置源。** 订阅地址仍然是 edgetunnel 的 `/sub`，节点来源在 edgetunnel 后台的「自定义优选IP」框里换成 `nodes.txt` 网址。后台保存之后，在 Clash Verge 里刷新订阅即可拿到新节点。

1. 确认 edgetunnel 后台已填入 `https://<用户名>.github.io/<仓库名>/nodes.txt` 并保存。
2. Clash Verge → 订阅（Profiles）→ 找到 edgetunnel 那一项 → 点右上角刷新图标。卡片上的时间会变成刚刚。
3. 进入「代理」页，选中链式代理 / 住宅IP 对应的组，点测速（闪电图标）。能出现延迟数字的就是可用节点。
4. 打开 https://ipinfo.io 或 https://ip.sb，确认出口 IP 的国家和运营商符合预期（日本 / 韩国的住宅或 ISP 地址）。

### 订阅刷新失败：先看日志

Clash Verge 的日志在 `%APPDATA%\io.github.clash-verge-rev.clash-verge-rev\logs\latest.log`，搜索「订阅更新」。常见信息：

| 日志 | 含义 | 处理 |
|---|---|---|
| `tls handshake eof` / `SSL connection could not be established` | 域名解析不到或 Worker 不存在 | 见 04 排错「订阅域名失效」 |
| `HTTP 401/403` | 订阅 token 变了 | 到 edgetunnel `/admin` 复制新的订阅地址，在 Clash Verge 里编辑该订阅的 URL |
| 刷新成功但没有新节点 | 后台没保存 `nodes.txt` 地址，或 Actions 还没产出 | 访问 `nodes.txt` 网址确认有内容，再回后台检查 |