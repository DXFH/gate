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