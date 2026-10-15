#!/usr/bin/env python3
"""Build src/vpngate.py from upstream hezhanleiok/gate with circuit-breaker / retry hardening."""
import re, sys
up = "/mnt/h/lab/cloud-iac/gate/upstream/gate/vpngate.py"
out = "/mnt/h/lab/cloud-iac/gate/src/vpngate.py"
s = open(up, encoding="utf-8").read()

def rep(old, new, count=1):
    global s
    assert s.count(old) == count, f"pattern count {s.count(old)} != {count}: {old[:60]!r}"
    s = s.replace(old, new)

# 1. imports
rep("import sys\nimport time\n", "import random\nimport sys\nimport threading\nimport time\n")

# 2. config: DOMAIN secret + resilience knobs
rep('WORKER_CHECK_URL = os.environ.get("CHECK_WORKER", "https://你的域名/check?sstp=vpn:vpn@")',
'''# 检测 Worker 完整 Endpoint 只从环境变量读取 (GitHub Secret: DOMAIN), 代码/产物里不出现明文
WORKER_CHECK_URL = (os.environ.get("DOMAIN") or os.environ.get("CHECK_WORKER") or "").strip()
RETRY_ATTEMPTS = max(1, int(os.environ.get("RETRY_ATTEMPTS", "3")))        # 单次 HTTP 抓取/检测最多尝试次数
RETRY_BASE_DELAY = float(os.environ.get("RETRY_BASE_DELAY", "1.5"))        # 指数退避基数(秒)
BREAKER_THRESHOLD = max(1, int(os.environ.get("BREAKER_THRESHOLD", "25"))) # 连续 N 次 Worker 异常 => 熔断
MIN_SUCCESS_TO_PUBLISH = max(1, int(os.environ.get("MIN_SUCCESS_TO_PUBLISH", "1")))
STRICT = os.environ.get("STRICT", "0") == "1"                              # STRICT=1 时才允许以 exit 1 结束''')

# 3. soft-fail instead of die()/exit(1) + retry helper + GITHUB_OUTPUT
rep('''def die(msg):
    log("FATAL", f"[失败] {msg}")
    sys.exit(1)''',
'''def set_output(key, value):
    """写入 GitHub Actions step output (本地运行时无此变量, 忽略)。"""
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as f:
            f.write(f"{key}={value}\\n")

def warn(msg):
    log("WARNING", f"[警告] {msg}")
    if os.environ.get("GITHUB_ACTIONS"):
        print(f"::warning::{msg}", flush=True)

def die(msg):
    """软失败: 告警 + publish=false + exit 0, 保留上一次已发布的 Pages。STRICT=1 才 exit 1。"""
    warn(msg)
    set_output("publish", "false")
    sys.exit(1 if STRICT else 0)

class SoftFail(Exception):
    pass

def http_get(url, *, timeout, headers=None, session=None, attempts=None, label="HTTP"):
    """带指数退避+抖动的 GET; 5xx/429/网络异常重试, 4xx(非429)直接返回。"""
    attempts = attempts or RETRY_ATTEMPTS
    getter = (session or requests).get
    last = None
    for i in range(1, attempts + 1):
        try:
            r = getter(url, timeout=timeout, headers=headers or {})
            if r.status_code < 500 and r.status_code != 429:
                return r
            last = RuntimeError(f"HTTP {r.status_code}")
        except requests.RequestException as exc:
            last = exc
        if i < attempts:
            delay = RETRY_BASE_DELAY * (2 ** (i - 1)) + random.uniform(0, 0.5)
            log(label, f"第 {i}/{attempts} 次失败({type(last).__name__}: {last}), {delay:.1f}s 后重试")
            time.sleep(delay)
    raise last''')

# 4. fetchers use retry helper
rep('resp = requests.get(VPNGATE_API, timeout=HTTP_TIMEOUT, headers={"User-Agent": "Mozilla/5.0 (compatible; gate-checker)"})',
    'resp = http_get(VPNGATE_API, timeout=HTTP_TIMEOUT, headers={"User-Agent": "Mozilla/5.0 (compatible; gate-checker)"}, label="VPN GATE")')
rep('resp = requests.get(VPNGATE_MIRROR, timeout=HTTP_TIMEOUT, headers={"User-Agent": "Mozilla/5.0"})',
    'resp = http_get(VPNGATE_MIRROR, timeout=HTTP_TIMEOUT, headers={"User-Agent": "Mozilla/5.0"}, label="VPN GATE")')
rep('resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})',
    'resp = http_get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"}, attempts=2, label="OPTIMAL API")')

# 5. circuit breaker + retrying check_one
rep('''def check_one(node, session):
    url = WORKER_CHECK_URL''',
'''class Breaker:
    """连续 N 次 Worker 异常 (超时/5xx/连接失败) 即熔断, 后续节点不再打 Worker。任何一次正常响应都会清零计数。"""
    def __init__(self, threshold):
        self.threshold = threshold
        self.consecutive = 0
        self.tripped = False
        self.lock = threading.Lock()
    def ok(self):
        with self.lock:
            self.consecutive = 0
    def fail(self):
        with self.lock:
            self.consecutive += 1
            if self.consecutive >= self.threshold and not self.tripped:
                self.tripped = True
                warn(f"熔断触发: 连续 {self.consecutive} 次 Worker 异常, 停止后续检测")

BREAKER = Breaker(BREAKER_THRESHOLD)

def check_one(node, session):
    if BREAKER.tripped:
        out = dict(node)
        out.update(protocol="sstp", status="failed", success=False, error="skipped: circuit open",
                   worker_error=True, skipped=True, exit=None, residential="unknown")
        return out
    url = WORKER_CHECK_URL''')

rep('''    try:
        r = session.get(url, timeout=CHECK_TIMEOUT, headers={"User-Agent": "Mozilla/5.0 (gate-checker)"})
        if r.status_code != 200:
            out["error"] = f"HTTP {r.status_code}"
            out["worker_error"] = True
            return out
        j = r.json()
        ok = bool(j.get("success"))''',
'''    try:
        # Worker 瞬时故障(超时/5xx/429)重试; 熔断后立即放弃
        r, err = None, "circuit open"
        for attempt in range(1, RETRY_ATTEMPTS + 1):
            if BREAKER.tripped:
                break
            try:
                r = session.get(url, timeout=CHECK_TIMEOUT, headers={"User-Agent": "Mozilla/5.0 (gate-checker)"})
                if r.status_code < 500 and r.status_code != 429:
                    break
                err = f"HTTP {r.status_code}"
            except requests.RequestException as exc:
                r, err = None, f"{type(exc).__name__}: {exc}"
            if attempt < RETRY_ATTEMPTS:
                time.sleep(RETRY_BASE_DELAY * (2 ** (attempt - 1)) + random.uniform(0, 0.5))
        if r is None or r.status_code >= 500 or r.status_code == 429:
            BREAKER.fail()
            out["error"] = err
            out["worker_error"] = True
            return out
        if r.status_code != 200:
            out["error"] = f"HTTP {r.status_code}"
            out["worker_error"] = True
            BREAKER.fail()
            return out
        try:
            j = r.json()
        except ValueError:
            out["error"] = "Worker 返回非 JSON"
            out["worker_error"] = True
            BREAKER.fail()
            return out
        BREAKER.ok()
        ok = bool(j.get("success"))''')

# 6. never publish the Worker endpoint in data.json
rep('"worker": WORKER_CHECK_URL,', '"worker": "(hidden: configured via GitHub Secret DOMAIN)",')

# 7. main(): guards
rep('''    session = requests.Session()
    rows, source = fetch_vpngate()''',
'''    if not WORKER_CHECK_URL:
        die("未配置检测 Worker: 环境变量 DOMAIN (GitHub Secret) 为空, 跳过本次运行并保留上次发布内容")
    if "://" not in WORKER_CHECK_URL or "sstp=" not in WORKER_CHECK_URL:
        die("DOMAIN 格式不正确, 期望形如 https://<worker>.workers.dev/check?sstp=vpn:vpn@")
    set_output("publish", "false")  # 默认不发布, 成功生成有效结果后才置 true
    session = requests.Session()
    rows, source = fetch_vpngate()''')

rep('''    if uniq and not success and len(worker_errors) == len(uniq):
        die("Worker 全部请求异常, 检测服务不可用 — 本次运行判定失败 (不生成空结果)")
''',
'''    if BREAKER.tripped:
        warn(f"熔断已触发, 本轮 {sum(1 for r in results if r.get('skipped'))} 个节点未检测")
    if uniq and not success and len(worker_errors) == len(uniq):
        die("Worker 全部请求异常, 检测服务不可用 — 保留上次发布的 nodes.txt, 本次不发布 (不生成空结果)")
    if len(success) < MIN_SUCCESS_TO_PUBLISH:
        die(f"可用节点 {len(success)} 个, 低于发布阈值 {MIN_SUCCESS_TO_PUBLISH} — 保留上次发布内容")
''')

rep('''    log("WEBSITE", "完成 (GitHub Pages 部署由 workflow 执行)")''',
'''    set_output("publish", "true")
    set_output("available", str(len(success)))
    log("WEBSITE", "完成 (GitHub Pages 部署由 workflow 执行)")''')

# 8. top-level handler: unexpected exceptions are soft failures too
rep('''    except Exception as exc:
        die(f"程序异常: {type(exc).__name__}: {exc}")''',
'''    except Exception as exc:
        die(f"程序异常: {type(exc).__name__}: {exc}")''')

open(out, "w", encoding="utf-8").write(s)
print("patched ->", out, len(s), "bytes")