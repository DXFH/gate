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