# 04 常见报错与排错

## Exit Code 1（Worker 校验失败）

**现象**：Actions 步骤「Fetch VPN Gate nodes…」红色失败，日志末尾 `Process completed with exit code 1`。

**常见原因与排查顺序**

1. **`DOMAIN` 为空或不存在**：日志里会看到未配置检测地址的警告。到仓库 Settings → Secrets 确认存在 `DOMAIN`，或运行 `pulumi stack output domainSecretName`。
2. **DOMAIN 格式不对**：必须是完整检测地址并以 `?sstp=vpn:vpn@` 结尾，脚本会在后面拼接 `host:port`。用下面命令直接验证：
   ```bash
   curl -sS "<DOMAIN 的值>1.1.1.1:443"
   ```
   返回 JSON（即使 `success:false`）说明 Worker 在线；超时或 5xx 说明 Worker 有问题。
3. **Worker 短暂无响应 / 网络波动**：当前脚本会重试（指数退避），连续 `BREAKER_THRESHOLD` 次异常后熔断，输出 warning，以 exit 0 结束并 `publish=false`，保留上一次的 `nodes.txt`。只有设置 `STRICT=1` 才会退出 1。
4. **上游数据源不可用**：官方 API 失败时自动切换镜像源，两个都失败才会无节点。

**自测结果**见 `05-test-report.md`。

## Actions 权限 403

**现象**：部署 Pages 或推送时报 `Resource not accessible by integration` / `403`。

**精准排查**

1. 检查仓库 Workflow Permissions：
   ```bash
   curl -sS -H "Authorization: Bearer $GITHUB_TOKEN" \
     https://api.github.com/repos/DXFH/gate/actions/permissions/workflow
   ```
   应看到 `default_workflow_permissions: "write"`。
2. 若不是，用 API 修复（需要令牌有仓库 Administration 写权限）：
   ```bash
   curl -X PUT -H "Authorization: Bearer $GITHUB_TOKEN" \
     https://api.github.com/repos/DXFH/gate/actions/permissions/workflow \
     -d '{"default_workflow_permissions":"write","can_approve_pull_request_reviews":false}'
   ```
3. 确认工作流里有 `permissions: pages: write` 和 `id-token: write`。
4. 确认 Pages 来源是 GitHub Actions：Settings → Pages → Source；或 API 返回 `build_type: workflow`。

## 其他坑

- **Pages 目录**：GitHub Pages 的分支发布只支持 `/` 或 `/docs`，不支持 `/public`。本项目使用 Actions 部署，直接上传 `public/` 产物，没有这个限制。
- **Secret 不会在日志里显示**：这是正常的，被遮盖为 `***`。
- **Pulumi 警告 `plaintextValue is deprecated`**：只是提示，不影响结果。
- **workers.dev 子域**：必须已在 Cloudflare 账号注册，否则 Worker 地址无法访问。
## 补充：从社区教程与评论里总结的坑

### 「[失败] Worker 全部请求异常, 检测服务不可用」+ exit code 1

这是上游原版脚本的行为：Worker 全部请求异常就判定失败退出。教程评论区里多人遇到，常见原因：

1. 原版工作流里写死了别人的 `CHECK_WORKER` 地址（`check.helei.kdns.fr`），没有改成自己的。**本项目不存在这个问题**：地址只从 Secret `DOMAIN` 读取，代码里没有任何默认的 Worker 地址。
2. 自己的 Worker 被 Cloudflare 封停或额度用尽（见下）。
3. 本项目的处理：同样的情况只输出 warning，exit 0，保留上一次的 `nodes.txt`。

### 「获取原始节点 -1」或节点数为 0

按顺序排查：

1. 看 Cloudflare 的通知邮件：如果是**每日 10 万次请求额度用完**，第二天会自动恢复。
2. 如果邮件说检测到**滥用**，Worker 会被删除。需要重新部署（本项目重新执行 `bash scripts/10-deploy-pulumi.sh` 即可），并降低运行频率。
3. 都不是的话，换一个优选域名或优选 API（见 03 运维指南的仓库变量）。

### Cloudflare 老是封我的域名

- 检测 Worker 没有内置密码，**不要公开分享它的地址**。本项目把地址放在 Secret `DOMAIN` 中，不会出现在日志里。
- 不要把定时频率设得太高，推荐 1 到 2 小时。
- 仍被封的话，可以改用 Cloudflare Pages 部署 edgetunnel（社区作者的建议）。

### 第一次运行成功，后面不自动执行

见 03 运维指南「定时任务不自动跑了怎么办」：默认分支、60 天不活动自动停用、首次延迟。

### 旧教程的写法在本项目里不适用

| 旧教程写法 | 本项目 |
|---|---|
| 手动编辑 `vpngate.py` 改 Worker 地址 | 用 Secret `DOMAIN`，不改代码 |
| 在 `vpngate.py` 里填 `EDT_UUID`、`EDT_DOMAIN` 生成 `sub.txt` | 不需要。UUID 和域名只属于 edgetunnel，本项目只提供 `nodes.txt` |
| 粘贴 `hosts.txt` 到后台 | 旧版文件名，现在填 `nodes.txt` 的网址 |
| Pages 目录选 `/public` | Pages 来源选 GitHub Actions，直接上传 `public/` 产物 |
| 工作流里再写一步用 API 开启 Pages | `scripts/20-publish-repo.sh` 已处理 |
### 订阅域名失效：Clash Verge 里 edgetunnel 订阅「几天前更新」，刷新一直失败

**现象**：订阅卡片的更新时间停在几天前，日志出现 `tls handshake eof`，但其他订阅正常。

**排查（命令在 WSL 或 PowerShell 里运行）**：

1. 绕过 Clash 的 fake-ip 查真实解析（Clash 开着时，系统 DNS 会返回 `198.18.x.x`，那是假地址，不能用来判断）：
   ```bash
   curl -sS -H "accept: application/dns-json" "https://1.1.1.1/dns-query?name=<你的edgetunnel域名>&type=A"
   ```
   返回 `"Status":3` 就是 NXDOMAIN，说明 DNS 记录已经被删掉了。
2. 到 Cloudflare 控制台确认：Workers 里是否还有 edgetunnel、该 Worker 的「自定义域」是否还在、DNS 里是否有对应记录。
3. 删除 Worker 时，它的自定义域和 DNS 记录会一起消失。KV 命名空间和 `ADMIN` 变量需要重新绑定。

**修复**：按 06 练习指南第 2 步重新部署 edgetunnel（Worker + `ADMIN` 变量 + 名为 `KV` 的绑定 + 自定义域），登录 `/admin` 填入 `nodes.txt` 网址，然后在 Clash Verge 里编辑 edgetunnel 订阅的 URL（新部署会生成新的 UUID 和订阅 token），再刷新。
## 坑：在 /admin 点「重置」后节点数骤降、全部 timeout

现象：重置后订阅只有 16 个节点，名称不再带「住宅」，或 Clash 里整组 timeout。
原因：
1. 重新部署若复用旧的 KV，旧的 config.json 里 HOSTS 会指向旧的 Pages 域名，节点的 SNI/Host 与 UUID 不匹配，所有节点超时。解决：访问 /admin/init 重置，让 HOSTS 回到当前 Worker 域名。
2. 重置会把「优选订阅生成 → 本地IP库 → 随机IP」恢复为 true，且随机数量为 16，此时订阅忽略 ADD.txt（nodes.txt）。解决：把随机IP改为 false、随机数量改为 72 以上，再保存。
3. 重置不会清除 ADD.txt，但仍建议先备份：GET /admin/config.json 与 /admin/ADD.txt。
验证：订阅里 type: vless 的数量应等于 nodes.txt 的行数；Clash 里更新 provider 后对「免费住宅IP」组做组延迟测试，应有延迟数字。
