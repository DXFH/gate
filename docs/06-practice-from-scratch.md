# 06 从零练习指南

适合把项目删掉后重新练习。分两条路线：**A 网页手动**（理解每一步），**B 脚本自动**（本项目）。建议先走 A 一遍，再走 B 对照。

## 先决条件

- Cloudflare 账号（免费）、GitHub 账号（免费）、一个已转入 Cloudflare 的域名（给 edgetunnel 绑定自定义域，推荐）。
- 不要把令牌写进文档或聊天。放在 WSL 的 `~/.cloud-iac.env` 与 `~/.cloudflare-deploy.env`。

## 路线 A：网页手动（社区教程流程，已修正易错点）

1. **部署检测 Worker**：Fork `lsh8848/cm-Workers-CheckSocks5`，Cloudflare 控制台 → Workers 和 Pages → 创建 Worker（名字例如 `check-sstp`），把 `_worker.js` 全部粘贴进去并部署。记下 `https://check-sstp.<你的子域>.workers.dev`。访问能看到检测页面即成功。
2. **部署 edgetunnel**：再创建一个 Worker（例如 `edgetunnel`），粘贴 `cmliu/edgetunnel` 的 `_worker.js`。然后：
   - 设置 → 变量：添加 `ADMIN`，值为管理员密码。
   - 设置 → 绑定：添加 **KV 命名空间**，变量名必须是 `KV`。
   - 触发器：添加自定义域名（推荐）。
   - 访问 `https://你的域名/admin` 登录。
3. **Fork `hezhanleiok/gate`**（或用本项目的 `src/` 与 `.github/`）。
4. **添加 Secret `DOMAIN`**：Settings → Secrets and variables → Actions → New repository secret，值为完整检测地址，**以 `?sstp=vpn:vpn@` 结尾**：
   `https://check-sstp.<你的子域>.workers.dev/check?sstp=vpn:vpn@`
5. **工作流读取 Secret**：原版要把 `CHECK_WORKER` 改成 `${{ secrets.DOMAIN }}`；本项目已经是这样。同时把 `NODES_URL` 里的用户名改成你自己的。
6. **开启 Actions 权限**：Settings → Actions → General → Workflow permissions → Read and write permissions → Save。
7. **启用 Pages**：Settings → Pages → Source 选 **GitHub Actions**。
8. **手动运行**：Actions → VPN Gate Node Check → Run workflow，等 1 到 3 分钟变绿。
9. **验证**：打开 `https://<用户名>.github.io/<仓库名>/nodes.txt`，应看到一行一个节点。
10. **接入 edgetunnel**：`/admin` → 「自定义优选IP」→ 填入上面的 `nodes.txt` 网址 → 保存。客户端订阅 edgetunnel 的订阅地址即可。

## 路线 B：脚本自动（本项目）

```bash
cd /mnt/h/lab/cloud-iac/gate
bash tests/run_tests.sh            # 本地故障注入测试，先确认脚本逻辑
bash scripts/10-deploy-pulumi.sh   # Worker + 仓库 + Secret DOMAIN（会先 refresh，手动删过的资源会被重建）
bash scripts/20-publish-repo.sh    # 推送代码、开 Actions 读写权限、启用 Pages、触发首次运行
```

edgetunnel 本身（第 2 步）仍需在网页上做，或用你已有的那一份。

## 练习用的删除与重来

```bash
cd /mnt/h/lab/cloud-iac/gate/pulumi
export PATH=$HOME/.pulumi/bin:$PATH PULUMI_CONFIG_PASSPHRASE=""
pulumi login file://$HOME/.pulumi-gate-state
pulumi destroy --yes               # 删除 Worker、仓库、Secret
```

之后重新执行路线 B 的三条命令即可。注意：`destroy` 会删除 GitHub 仓库 `gate`，其中的 Actions 运行记录一并消失。

## 验收清单

- [ ] Worker 地址 `.../check?sstp=vpn:vpn@1.1.1.1:443` 返回 JSON
- [ ] 仓库 Secret 里有 `DOMAIN`
- [ ] Workflow permissions 为 read and write
- [ ] Actions 运行全部步骤绿色
- [ ] `nodes.txt` 返回 200 且有内容
- [ ] edgetunnel `/admin` 里已填入 `nodes.txt` 网址