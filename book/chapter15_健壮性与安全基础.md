---
jupytext:
  text_representation:
    extension: .md
    format_name: myst
    format_version: '0.13'
    jupytext_version: 1.16.4
kernelspec:
  display_name: Python 3
  language: python
  name: python3
---

# 第15章 健壮性与安全基础

> 为什么在收尾阶段讲安全？M2 已能对外提供 `/api/upload`、`/api/health` 等端点，但“能跑”不等于“能扛住真实流量”。一个带后缀 `.wav` 的伪造文件就能绕过扩展名检查、一个循环脚本就能把单进程打满、前端跨域请求在浏览器里被静默阻断——这些都是上线前必须堵住的口子。本章以后端加固为主线：先学会在边界做**输入校验**（魔数、Content-Length 预检），再用**限流**给 API 加“闸门”、用**密钥管理**守住配置、并讲清“**纯静态跨源直连为何需要 CORS**”（`http://localhost` 的 nginx 静态页调 `http://localhost:8000` 的 API，哪怕同主机也算跨源），最后用转义守住 **XSS**。学完你能给 M2 加上最小可用、且可被测试证明的健壮性与安全层，并把“认证”留作作业自行补齐。

## 学习目标

完成本章后，你将能够：

1. 能编写基于**魔数（magic bytes）**与 `Content-Length` 预检的上传校验，解释“只验扩展名为何可被伪文件绕过”。
2. 能实现进程内**固定窗口限流（fixed-window rate limiting）**，用可注入时钟的 `is_allowed` 纯函数证明“去掉限流可被刷”。
3. 能解释**同源策略（Same-Origin Policy）**与 **CORS** 的协作关系，说明“纯静态跨源直连（`http://localhost` → `http://localhost:8000`）为何仍需 CORS 白名单”，并用纯函数实现源（Origin）判定。
4. 能对动态内容做 **XSS（Cross-Site Scripting）转义**，说明何时需要转义、何时由框架自动转义，并用 hermetic 测试证明。

## 先修要求

- 完成 [第7章 HTTP 与 REST API](chapter07_HTTP与REST_API.md)（理解状态码 400/413/429 语义与 FastAPI 依赖）与 [第11章 M2 可用 Web API](chapter11_里程碑M2_WebAPI.md)（已有一个可上传/查询的 Web API）。
- 会读 MeetingToText 只读参考：`backend/app/middleware/ratelimit.py`（固定窗口实现）、`backend/app/routers/upload.py`（魔数与 `Content-Length` 双重校验）、`backend/app/routers/health.py`（只读探针）、`backend/app/config.py` 的 `cors_origins_from_env()`。
- Python 基础：`bytes.startswith`、`os.path.splitext`、`threading.Lock`。

## 正文

### 15.1 输入校验：扩展名、魔数、Content-Length 与空文件

“输入校验”只在信任边界做一次（parse, don't validate）：请求进入 `upload.py` 就判定合法/不合法，内部不再反复猜。MeetingToText 的 `POST /api/upload` 按三道闸门顺序校验——与习题 `solution.py` 的纯函数一一对应：

| 闸门 | 验什么 | 未通过的响应 | 为什么需要 |
|---|---|---|---|
| 扩展名 | `os.path.splitext(filename)[1].lower() in ALLOWED_EXTENSIONS` | `400 不支持的文件格式` | 第一道粗筛，拒绝明显非法类型 |
| `Content-Length` 预检 | `int(request.headers["content-length"]) > max_size` | `413 文件超过 500MB 限制` | 在读盘前就拒绝超大请求，避免浪费 I/O 与磁盘 |
| 魔数 | `header.startswith(b"RIFF")` 等容器签名 | `400 文件内容与音频格式不符` | 防止“改后缀的伪文件”过检（见改动并预测实验 1） |
| 空文件/溢出写盘 | `written == 0` 或 `overflow` | `400 空文件` / `413` | 兜底，避免产生 0 字节任务 |

密钥管理（key management）同属“输入/配置校验”：`llm_api_key` 等敏感值**只从环境变量或 `MTT_*` 配置读**，永不写进代码仓库；日志与错误响应必须脱敏（`map_llm_error` 的中文脱敏映射即是例子）。本章不讲密码学，只讲“密钥不落地、不回显、不进前端”。

```{code-cell} ipython3
# 15.1 可执行示例：魔数校验与 Content-Length 预检（hermetic 纯函数）
import os

ALLOWED_EXTENSIONS = {".wav", ".mp3", ".m4a", ".flac", ".ogg", ".webm", ".opus", ".aac", ".wma"}

def _is_valid_magic(ext: str, header: bytes) -> bool:
    if len(header) == 0:
        return True  # 空文件由后续分支单独报“空文件”
    if ext == ".wav":
        return header.startswith(b"RIFF")
    if ext == ".flac":
        return header.startswith(b"fLaC")
    if ext in (".ogg", ".oga", ".opus"):
        return header.startswith(b"OggS")
    if ext == ".mp3":
        return header.startswith(b"ID3") or (len(header) >= 2 and header[0] == 0xFF and (header[1] & 0xE0) == 0xE0)
    if ext in (".m4a", ".mp4"):
        return len(header) >= 8 and header[4:8] == b"ftyp"
    if header.startswith(b"\x1aE\xdf\xa3"):
        return True
    return False

def check_content_length(content_length: str | None, max_size: int) -> tuple[bool, str | None]:
    """预检 Content-Length。返回 (是否通过, 错误信息)。None 表示无头可跳过。"""
    if content_length is None:
        return True, None
    try:
        cl = int(content_length)
    except ValueError:
        return True, None  # 非法头按缺失处理，由写盘阶段兜底
    if cl > max_size:
        return False, f"文件超过 {max_size // (1024*1024)}MB 限制"
    return True, None

# 演示：真 wav 头 vs 伪 wav（文本冒充）
print(_is_valid_magic(".wav", b"RIFF....WAVE"))  # True
print(_is_valid_magic(".wav", b"hello world"))   # False  <- 伪文件被拦
print(_is_valid_magic(".mp3", b"ID3\x03\x00"))   # True
print(_is_valid_magic(".mp3", b"\xff\xfb\x90\x00"))  # True (frame sync)
print(check_content_length("600000000", 500*1024*1024))  # False, 413
print(check_content_length(None, 500*1024*1024))         # True, 无头跳过
print(check_content_length("not-a-number", 500*1024*1024))  # True, 非法头跳过
assert _is_valid_magic(".wav", b"RIFFxxxx") is True
assert _is_valid_magic(".wav", b"BAD!") is False
print("—— 断言通过：扩展名可骗，魔数不可骗；超限在读盘前即拦 ——")
```

只验扩展名而不验魔数，攻击者把 `virus.exe` 重命名为 `meeting.wav` 即可过检——故“去魔数校验 → 伪文件过检”是本章必做的预测实验。

### 15.2 限流：固定窗口、Retry-After 与单进程 caveat

限流（rate limiting）是“以可控的拒绝换取整体可用”。MeetingToText 用**固定窗口（fixed-window）**：每 60 秒为一窗，每 IP 计数 `rpm` 次，超限返回 `429 Too Many Requests` + `Retry-After` 头，窗口滚动后重置。

`backend/app/middleware/ratelimit.py` 的 `InMemoryRateLimiter` 可注入时钟 `_now`，故测试可 hermetic 地快进时间而无需 `sleep`：

```{code-cell} ipython3
# 15.2 可执行示例：固定窗口限流纯函数（可注入时钟，hermetic）
import threading, time
from collections.abc import Callable

class InMemoryRateLimiter:
    def __init__(self, rpm: int = 60, window_seconds: int = 60, _now: Callable[[], float] = time.time):
        self.rpm = rpm
        self.window_seconds = window_seconds
        self._now = _now
        self._store: dict[str, tuple[float, int]] = {}
        self._lock = threading.Lock()
    def is_allowed(self, key: str) -> tuple[bool, int]:
        now = self._now()
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._store[key] = (now, 1)
                return True, 0
            window_start, count = entry
            elapsed = now - window_start
            if elapsed >= self.window_seconds:
                self._store[key] = (now, 1)
                return True, 0
            if count < self.rpm:
                self._store[key] = (window_start, count + 1)
                return True, 0
            retry_after = int(self.window_seconds - elapsed)
            return False, max(1, retry_after)
    def reset(self):
        with self._lock:
            self._store.clear()

# 用可控时钟演示：rpm=3，窗口 60s，同一 IP 第 4 次被限
clock = [0.0]
limiter = InMemoryRateLimiter(rpm=3, window_seconds=60, _now=lambda: clock[0])
for i in range(5):
    ok, retry = limiter.is_allowed("192.168.1.10")
    print(f"req {i+1}: allowed={ok} retry_after={retry}")
    # 前 3 次 True，第 4 次 False + retry 60
clock[0] = 61  # 快进到下一窗口
print("after window roll:", limiter.is_allowed("192.168.1.10"))  # True, 新窗口
# 不同 IP 互不影响
print("other ip:", limiter.is_allowed("10.0.0.1"))

assert limiter.is_allowed("x")[0] is True
limiter2 = InMemoryRateLimiter(rpm=2, _now=lambda: 0)
assert limiter2.is_allowed("k")[0] is True
assert limiter2.is_allowed("k")[0] is True
assert limiter2.is_allowed("k")[0] is False  # 第 3 次超限
print("—— 断言通过：同窗计数、跨窗重置、IP 隔离 ——")
```

关键点：

- 只对 `/api/*` 限流，静态资源不限——`RateLimitMiddleware.__call__` 先判 `path.startswith("/api/")`。
- 429 响应仍需补 **CORS** 头，否则浏览器的跨源请求看到 429 却因缺 `Access-Control-Allow-Origin` 而报 CORS 错误、前端拿不到 `Retry-After`（`ratelimit.py` 内已对 429 补 CORS 头，见“去 CORS 白名单”实验）。
- `threading.Lock` 保护 `dict` 读写；在 `--workers 1` 时精确，`workers>1` 时每进程独立计数、全局有效限额为 `rpm * workers`（`config.MTT_RATE_LIMIT_RPM` 文档已注明）。

### 15.3 XSS 与输出转义

XSS（Cross-Site Scripting，跨站脚本）的本质是“把不可信输入当成代码执行”。前端若用 `innerHTML = userInput` 直接插入转录文本，攻击者可在文件名或说话人文本中植入 `<script>`，被其他用户加载时执行。

防御分两层：

1. **框架自动转义**：Vue 3 的 `{{ text }}` 插值会自动对 HTML 特殊字符转义；只有显式 `v-html` 才需人工把关。
2. **服务端/工具层转义（本章练习设想）**：`m2t/export.py` 当前仅提供 TXT/SRT/MD 三种导出（不含 HTML），并未内置 `escape_html`；若后续需导出 HTML，则应对任务名、说话人、文本字段做假设性的 `escape_html`（`&→&amp; <→&lt; >→&gt; "→&quot; '→&#x27;`），避免拼接出可执行标签——本章将其作为 XSS 练习的假设场景，而非对 `export.py` 现有实现的描述。

```{code-cell} ipython3
# 15.3 可执行示例：XSS 转义（hermetic 纯函数）
import html

def escape_html(s: str) -> str:
    # html.escape 处理 &, <, >, " ；单引号需另补
    return html.escape(s, quote=True).replace("'", "&#x27;")

cases = [
    ("hello", "hello"),
    ("<script>alert(1)</script>", "&lt;script&gt;alert(1)&lt;/script&gt;"),
    ("a & b", "a &amp; b"),
    ('say "hi"', "say &quot;hi&quot;"),
    ("it's", "it&#x27;s"),
]
for inp, expected in cases:
    out = escape_html(inp)
    print(f"{inp!r} -> {out!r}  {'OK' if out==expected else 'FAIL'}")
    assert out == expected
# 转义后可安全拼进 HTML 模板，而不产生可执行标签
template = "<div>{}</div>"
print(template.format(escape_html("<img onerror=alert(1) src=x>")))
print("—— XSS 转义恒等：转义后无 <script> 可执行 ——")
```

经验：永远在“输出边界”转义，而非“输入时”——同一份转录文本可能既要导出 HTML 也要导出纯文本，输入侧转义会污染后者。

### 15.4 CORS：浏览器同源策略与纯静态跨源直连

**同源策略（Same-Origin Policy）**是浏览器的安全基线：协议（protocol）+ 主机（host）+ 端口（port）三者任一不同即为**跨源（cross-origin）**。默认跨源的 `fetch/XHR` 会被浏览器阻断，除非服务端通过 **CORS（Cross-Origin Resource Sharing，跨源资源共享）**显式允许。

**为何纯静态跨源直连需要 CORS？** MeetingToText 的生产形态是“纯静态托管 + 跨源直连”（容器部署小节已讲 `VITE_API_BASE_URL`）：

- 前端由 nginx 在 `http://localhost:80`（`http://localhost`）以**纯静态文件**形式托管；
- 后端在 `http://localhost:8000` 提供 JSON API；
- 浏览器在 `http://localhost` 打开页面后，用 `fetch("http://localhost:8000/api/health")` 直连后端。

虽然同主机（localhost），但 **`:80` 与 `:8000` 端口不同 ⇒ 跨源**。若后端响应缺 `Access-Control-Allow-Origin`，浏览器会在 JS 侧抛 CORS 错误、前端拿不到数据——**哪怕 `curl` 能通**（`curl` 不受同源策略约束）。开发期的 `http://localhost:5173`（vite dev）→ `http://localhost:8000` 同理跨源。

MeetingToText 的 CORS 配置（`backend/app/config.py`）：

```python
def cors_origins_from_env() -> list[str]:
    raw = os.getenv("MTT_CORS_ORIGINS", "")
    if raw.strip() == "":
        return ["http://localhost:5173", "http://localhost:8000", "http://localhost"]
    return [p.strip() for p in raw.split(",") if p.strip()]
```

与 `backend/app/server.py` 的挂载：

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins_from_env(),
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

习题的 `is_origin_allowed` 即此逻辑的纯函数抽取——便于 hermetic 断言“白名单删 origin → 预测浏览器阻断”。

```{code-cell} ipython3
# 15.4 可执行示例：CORS 源判定纯函数
def is_origin_allowed(origin: str, allowlist: list[str]) -> bool:
    if "*" in allowlist:
        return True
    return origin in allowlist

DEFAULT_ALLOWLIST = ["http://localhost:5173", "http://localhost:8000", "http://localhost"]

# 演示：默认白名单
for o in ["http://localhost:5173", "http://localhost", "http://evil.com", "http://localhost:3000"]:
    print(o, "->", is_origin_allowed(o, DEFAULT_ALLOWLIST))

# 删掉 http://localhost 后，纯静态页的跨源直连将被阻断（改动并预测实验 3）
trimmed = [x for x in DEFAULT_ALLOWLIST if x != "http://localhost"]
print("trimmed allowlist:", trimmed)
print("http://localhost allowed after trim?", is_origin_allowed("http://localhost", trimmed))
assert is_origin_allowed("http://localhost:5173", DEFAULT_ALLOWLIST) is True
assert is_origin_allowed("http://evil.com", DEFAULT_ALLOWLIST) is False
assert is_origin_allowed("http://localhost", trimmed) is False
print("—— 断言通过：白名单缺 origin 则跨源请求被浏览器阻断 ——")
```

要点：

- `allow_credentials=False` 时不可搭配 `Allow-Origin: *` 回显具体源，后端需精确匹配。
- 预检（preflight）：浏览器对带自定义头/`Content-Type: application/json` 的跨源 `POST` 会先发 `OPTIONS`，`CORSMiddleware` 自动处理；若限流中间件对 429 漏补 CORS 头，预检通过但真实请求因 429 仍被视为 CORS 失败。
- 不要把 `VITE_API_BASE_URL` 写成相对路径指望同源——生产是双端口，相对路径会打到 nginx 而非后端。

### 15.5 应用：加固 M2

把 15.1–15.4 串成对 M2 的最小加固清单（对照 `upload.py` / `ratelimit.py` / `health.py` / `config.py`）：

1. 上传链路加魔数 + `Content-Length` 双重校验 + 空文件 400。
2. 全局 `RateLimitMiddleware` 仅对 `/api/*` 生效，429 带 `Retry-After` 与 CORS 头。
3. `GET /api/health` 探针返回 `200`（健康）或 `503`（`disk low` / `db error`），供容器 `healthcheck` 与编排器判定是否摘流。
4. 前端所有动态文本用插值而非 `v-html`；若为导出拼接 HTML，则在拼接前做 `escape_html` 练习（当前 `export.py` 的 TXT/SRT/MD 导出不涉及 HTML，故为假设性练习）。
5. CORS 白名单通过 `MTT_CORS_ORIGINS` 环境变量配置，默认即含 `http://localhost` 以支持纯静态跨源直连。

认证（Bearer token 中间件）留作本章作业（见 `answers/chapter15/auth_exercise.md`），正文不实现。

### 改动并预测

以下 3 个实验均可在本章 `{code-cell}` 或本地 `.venv` 中复现，按“改什么 → 预测 → 解释”三段式。每个实验均对应 `answers/chapter15/solution.py` 的一个纯函数，便于用 pytest 复证。

#### 改动并预测 实验 1：去掉魔数校验 → 预测伪文件过检

- **改什么**：把 `upload.py` 的 `_is_valid_magic(ext, header)` 调用删掉（或改为恒 `return True`），仅保留扩展名检查 `_allowed_file`。
- **预测**：将任意文本文件重命名为 `evil.wav`（内容为 `hello world`，头非 `RIFF`）再 `POST /api/upload`，**不再报** `400 文件内容与音频格式不符`，而是进入写盘与建任务流程（`200` 或后续 ASR 失败），伪文件**过检**。未改动前同样请求应得 `400`。
- **解释**：扩展名是用户可控的元数据，魔数是文件容器的客观签名；去掉魔数等于把“内容校验”降级为“文件名校验”，与本章 `test_is_valid_magic_rejects_fake_wav` 的 hermetic 断言一致——`_is_valid_magic(".wav", b"hello") is False` 在无魔数分支时恒为 `True`。

#### 改动并预测 实验 2：去掉限流 → 预测可被刷

- **改什么**：注释掉 `server.py` 的 `app.add_middleware(RateLimitMiddleware)` 或把 `MTT_RATE_LIMIT_RPM` 设为极大值（如 `100000`），重启后用脚本对 `GET /api/health` 连续发 100 次请求（同 IP、60s 内）。
- **预测**：未改动前第 `rpm+1` 次起应得 `429` 且带 `Retry-After`；去掉限流后 100 次**全部 `200`**，服务端无拒绝、可被单 IP 刷满 CPU/IO。可用本章 `InMemoryRateLimiter(rpm=60)` 的纯函数复证：`is_allowed` 的第 61 次在无计数时恒 `True`。
- **解释**：固定窗口计数器是“有状态的闸门”；移走闸门后，`is_allowed` 退化为恒真，攻击者可用低成本循环耗尽模型与磁盘资源，健康探针的 `503` 也因请求洪泛而更难被编排器及时感知。

#### 改动并预测 实验 3：CORS 白名单删 origin → 预测浏览器阻断

- **改什么**：把 `MTT_CORS_ORIGINS` 从默认 `http://localhost:5173,http://localhost:8000,http://localhost` 改为 `http://localhost:5173,http://localhost:8000`（删掉 `http://localhost`）。
- **预测**：`curl http://localhost:8000/api/health -H "Origin: http://localhost"` 仍得 `200`（curl 不受 CORS 约束），但浏览器在 `http://localhost` 打开前端页后 `fetch("/api/health")` 会在控制台报 `CORS policy: No 'Access-Control-Allow-Origin' header`，前端显示网络错误。还原白名单后即恢复。此行为与习题 `is_origin_allowed("http://localhost", trimmed) is False` 一致。
- **解释**：`http://localhost`（:80 的 nginx 静态页）→ `http://localhost:8000`（后端）是**跨源（端口不同）**，必须由后端在 `Access-Control-Allow-Origin` 中回显请求源才被浏览器放行；白名单缺一项即对该源恒阻断，且 429 分支若漏补 CORS 头会出现“限流后前端误判为 CORS 失败”的叠加故障。

## 习题

> 参考答案与测试在 `answers/chapter15/`，运行 `.venv/bin/pytest answers/chapter15/ -q` 验证。题目均为 hermetic 纯函数，不依赖网络或外部服务；认证作业为独立子目录 `auth_solution/`，同样由 pytest 驱动（`TestClient` 进程内断言 401）。

1. **魔数校验**：实现 `is_valid_magic(ext: str, header: bytes) -> bool`，按容器签名判定头是否匹配扩展名（`.wav→RIFF`、`.flac→fLaC`、`.ogg→OggS`、`.mp3→ID3` 或 frame sync、` .m4a→ftyp`、` .webm→EBML` 等），空头返回 `True`（由空文件分支另行处理）。
2. **Content-Length 预检**：实现 `check_content_length(content_length: str | None, max_size: int) -> tuple[bool, str | None]`，`None`/非法值视为跳过，超 `max_size` 返回 `(False, msg)`，否则 `(True, None)`。
3. **限流计数**：实现 `InMemoryRateLimiter`（或等价纯函数 `is_allowed`），固定窗口 60s、每 key 限 `rpm` 次、可注入时钟 `_now`，超限返回 `(False, retry_after)` 且 `retry_after>=1`，窗口滚动后重置，`reset()` 清空。
4. **CORS 源判定**：实现 `is_origin_allowed(origin: str, allowlist: list[str]) -> bool`，`"*"` 通配任意源，否则精确匹配；并实现 `cors_origins_from_env(raw: str) -> list[str]` 的纯函数版（空串返回默认三项，逗号分隔、去空、trim）。
5. **XSS 转义**：实现 `escape_html(s: str) -> str`，对 `& < > " '` 五字符转义，满足 `escape_html('<script>') == '&lt;script&gt;'` 等。
6. **认证（作业，见 `auth_exercise.md`）**：按规约给 M2 的 FastAPI 应用加 Bearer token 中间件，未带 `Authorization: Bearer {token}` 时对 `/api/*` 返回 `401`，带正确 token 放行；静态/健康探针等非 `/api/*` 不鉴权（或按作业规约实现）。参考解与断言在 `answers/chapter15/auth_solution/`。

## 延伸挑战

1. 为限流加“令牌桶（token bucket）”变体，对比固定窗口的边界突刺（burst at window edge），用可注入时钟证明两者差异。
2. 给 `POST /api/upload` 补“文件名规范化”：`../`、`\x00`、超长名（>200）等边界，写 hermetic 用例并与 `upload.py` 的 `safe_name = uuid + ext` 对照。
3. 把 `escape_html` 扩展为 Markdown 上下文转义（反引号、链接语法），并说明为何“输出时转义”优于“输入时转义”。
