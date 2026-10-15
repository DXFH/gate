# 05 自测与排错报告

测试时间：2026-10-15。环境：WSL Ubuntu，Python 3.12。

## 一、真实环境运行

| 项目 | 结果 |
|---|---|
| 官方 API 原始节点 | 96（线上运行 98） |
| SSTP 节点 | 86 |
| 去重后 | 86 |
| Worker 检测可用 | 43（本地）/ 56（线上首次运行） |
| 线上 Actions 运行 | 全部步骤 success，已部署 Pages |
| `nodes.txt` | HTTP 200，56 行 |
| 线上统计 | 国家 10 个，疑似住宅 55，疑似机房 1 |

线上 Worker 直接调用 `…/check?sstp=vpn:vpn@1.1.1.1:443` 返回 JSON 且 `success:false`，符合预期，说明 Worker 在线。

## 二、本地故障注入测试（`tests/run_tests.sh`）

| 用例 | 模拟 | exit | publish | nodes.txt 行数 |
|---|---|---|---|---|
| T1_no_domain | 未配置 DOMAIN | 0 | false | 0 |
| T2_ok | Worker 正常 | 0 | true | 40 |
| T3_timeout | Worker 超时 | 0 | false | 0 |
| T4_http500 | Worker 返回 500 | 0 | false | 0 |
| T5_garbage | 返回非 JSON | 0 | false | 0 |
| T6_http403 | Worker 返回 403 | 0 | false | 0 |
| T7_flaky | 间歇性失败 | 0 | true | 38 |
| T8_timeout_strict | 超时 + STRICT=1 | 1 | false | 0 |

## 三、结论

- 所有异常场景默认以 exit 0 结束并输出 warning，不再出现 Exit Code 1。
- 熔断在连续异常达到阈值后触发，输出「熔断触发」警告，不发布空结果，线上 Pages 保持上一版。
- 间歇性失败（T7）通过重试仍能产出结果。
- 只有显式设置 `STRICT=1`（T8）才会退出 1，用于需要强失败信号的场景。

## 四、已知限制

- VPN Gate 节点是志愿者提供的，可用数量会随时间波动。
- 「住宅」判断来自出口 ASN/组织名的关键词估计，不是绝对准确。
## 六、2026-10-15 追加：采用社区教程建议后的回归

改动：默认定时改为每 2 小时；`EDGE_HOSTS`、`OPTIMAL_API` 可用仓库变量覆盖（留空自动回退默认值）；部署脚本先 `pulumi refresh`，手动删除过的资源会被重建。

回归结果：T1 到 T8 全部与上表一致（T2 正常产出 43 行，T7 间歇性失败产出 46 行，T8 严格模式仍为 exit 1）。`EDGE_HOSTS` 设为空字符串时回退到内置的 20 个默认域名。

## v2 回归与新增测试（2026-10-15）

在 WSL 本地用 `tests/run_tests.sh` 运行，Worker 用 `tests/mock_worker.py` 模拟，VPN Gate 与优选 API 是真实网络。

| 用例 | 场景 | 结果 |
|---|---|---|
| T1–T8 | 无 DOMAIN / 正常 / 超时 / 500 / 乱码 / 403 / 间歇失败 / STRICT | 与首轮一致：故障类不发布且 exit 0，T7 重试后有产出，仅 STRICT=1 时 exit 1 |
| T9 | 三网文件生成 | `nodes-ct.txt` 26 个入口、`nodes-cu.txt` 24 个、`nodes-cmcc.txt` 28 个，每份行数与 `nodes.txt` 相同 |
| T10 | 入口池里混入 2 个不可连接入口 | 2 个被剔除，`nodes.txt` 里残留 0 行 |
| T11 | 入口全部不可连接 | 警告后保留原入口池，仍然 exit 0、有产出（设计如此：避免空池） |

注意事项：
- 本机 Clash 开着 TUN/fake-ip，对任何 IP 的 TCP 连接都会“成功”（`192.0.2.1` 也能连上），所以 T10/T11 用 `127.0.0.1:1`、`127.0.0.1:2`（拒绝连接）来模拟失效入口。这也说明入口探测要放在 Actions 里做，在本机跑没有意义。
- 每次运行的节点数不同（30–48），因为 VPN Gate 的节点本身在变，测试里还限制了检测数量 `MAX_CHECK_NODES=60`。
