---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

# 数据校验与防注入

> 学完本节，你能回答：SQL 注入如何通过字符串拼接发生？为什么占位符能根治它？XSS 与 CSRF 的攻击面分别为何处？校验与转义应分别放在哪一层？

## 注入的本质：把数据当代码执行

无论 SQL 注入还是 XSS，根因都是**把外部输入直接拼进了代码或标记的语法位**。正确做法是区分“代码结构”与“数据内容”，用“参数化”或“转义”让数据永远只是数据。

## SQL 注入：从拼接字符串到占位符

MeetingToText 的任务查询若写成字符串拼接：

```python
sql = f"SELECT * FROM tasks WHERE filename = '{user_input}'"
```

当 `user_input = "' OR '1'='1"` 时，SQL 变成 `WHERE filename = '' OR '1'='1'`，全表泄露。

参数化查询（`?` 或 `:name` 占位符）让驱动把“SQL 结构”与“参数值”分开传输，数据库按值比较，不做语法解析，从而根治拼接注入。下例用 `sqlite3` 对比不安全拼接与安全占位符，并演示 `m2t.store.TaskStore` 的占位符写法为何是安全的。

示例：SQL 注入与参数化：

```{code-cell} ipython3
import sqlite3, pathlib, tempfile

# 1) 准备内存数据库（模拟 m2t.store 的建表）
con = sqlite3.connect(":memory:")
con.row_factory = sqlite3.Row
con.executescript("""
CREATE TABLE tasks (id TEXT PRIMARY KEY, filename TEXT, status TEXT);
INSERT INTO tasks VALUES ('t1','meeting.wav','done');
INSERT INTO tasks VALUES ('t2','notes.wav','pending');
""")

# 2) 恶意输入：试图让条件恒真
malicious = "' OR '1'='1"

# 不安全：字符串拼接（仅演示，生产禁用）
unsafe_sql = f"SELECT * FROM tasks WHERE filename = '{malicious}'"
unsafe_rows = list(con.execute(unsafe_sql).fetchall())
print("unsafe rows:", len(unsafe_rows), "->", [r["id"] for r in unsafe_rows])

# 安全：占位符（sqlite3 的 qmark 风格）
safe_rows = list(con.execute("SELECT * FROM tasks WHERE filename = ?", (malicious,)).fetchall())
print("safe rows:", len(safe_rows))

# 3) 对比 m2t.store 的写法：参数元组而非插值
from m2t.store import TaskStore
with tempfile.TemporaryDirectory() as td:
    db = pathlib.Path(td) / "inject.db"
    store = TaskStore(db)
    store.create("t1", "meeting.wav", full_text="hello")
    # 即使按恶意输入查询，也只做值比较，不会注入
    row = store.get(malicious)
    print("store.get(malicious) is None:", row is None)
    assert len(unsafe_rows) == 2  # 拼接：全表泄露
    assert len(safe_rows) == 0    # 占位符：0 行
    assert row is None
# 预期输出:
# unsafe rows: 2 -> ['t1', 't2']
# safe rows: 0
# store.get(malicious) is None: True
```

> **环境约定**：本书面向 Linux，`sqlite3` 占位符在所有平台行为一致，均为 `?`（qmark）或 `:name`（named）。路径示例 `pathlib.Path(td) / "inject.db"` 统一为 `/`；示例中统一用 `/` 书写即可。

## XSS：转义输出而非过滤输入

跨站脚本（XSS）发生在“用户输入被当作 HTML/JS 原样渲染”时。例如把 `"<script>alert(1)</script>"` 存入会议标题后，前端若用 `innerHTML` 直接插入，就会执行脚本。

防御分两层：

1. **输入校验**：在后端用白名单校验长度、字符集与业务规则（如会议标题最长 200 字符），拒绝明显异常。
2. **输出转义**：在渲染层对 `& < > " '` 做 HTML 实体转义，或使用框架自带的转义（如 Vue 的 `{{ }}` 默认转义、`v-html` 才不转义）。CSP（Content Security Policy）可进一步限制脚本来源。

校验与转义的边界：校验是“拒绝不该进来的”，转义是“保证出去的不被当代码执行”。

示例：XSS 转义输出：

```{code-cell} ipython3
import html, re

def validate_title(s: str) -> str:
    s = s.strip()
    if not (1 <= len(s) <= 200):
        raise ValueError("标题长度需在 1-200 之间")
    # 业务白名单：允许中英文、数字、常见标点，拒绝控制字符
    if re.search(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", s):
        raise ValueError("标题含非法控制字符")
    return s

def render_title(raw: str) -> str:
    # 渲染前转义：把 < > & " ' 转为实体
    safe = html.escape(raw, quote=True)
    return f"<h1>{safe}</h1>"

# 正常输入
title = validate_title("第10章 健壮性与安全底线")
print(render_title(title))
# 恶意输入：试图注入脚本
attack = '<script>alert("xss")</script> & 会议'
print("escaped:", render_title(attack))
# 验证：转义后不再含 <script>
assert "&lt;script&gt;" in render_title(attack)
assert "<script>" not in render_title(attack)
# 白名单校验：控制字符被拒绝
try:
    validate_title("bad\x01title")
except ValueError as e:
    print("validation blocked:", e)
# 预期输出:
# <h1>第10章 健壮性与安全底线</h1>
# escaped: <h1>&lt;script&gt;alert(&quot;xss&quot;)&lt;/script&gt; &amp; 会议</h1>
# validation blocked: 标题含非法控制字符
```

## CSRF：用同步随机令牌守住“写操作”

跨站请求伪造（CSRF）利用浏览器自动携带 Cookie 的特性，诱导用户在已登录状态下向目标站点发送非预期请求。防御要点：

- **写操作需令牌**：对 `POST/PUT/DELETE` 要求携带与 Cookie 分离的 CSRF 令牌（`X-CSRF-Token` 头或表单隐藏域），服务端做常时间比较。
- **Cookie 属性**：`SameSite=Lax/Strict` 与 `HttpOnly` 减少跨站携带与脚本窃取。
- **来源校验**：对关键操作校验 `Origin` / `Referer`，但不作为唯一依据（部分场景会缺失）。

令牌生成宜用 `secrets.token_urlsafe` 等密码学随机数，并与会话或 JWT 的 `jti` 绑定，避免可预测。

示例：CSRF 同步令牌：

```{code-cell} ipython3
import secrets, hmac, hashlib

# 服务端密钥（仅服务端持有）
_CSRF_SECRET = b"csrf-secret-rotation-32bytes!!"

def issue_csrf_token(session_id: str) -> str:
    # 用 HMAC 绑定会话，避免令牌与会话脱节
    raw = secrets.token_urlsafe(32)
    mac = hmac.new(_CSRF_SECRET, f"{session_id}:{raw}".encode(), hashlib.sha256).hexdigest()[:16]
    return f"{raw}.{mac}"

def verify_csrf_token(token: str, session_id: str) -> bool:
    try:
        raw, mac = token.rsplit(".", 1)
    except ValueError:
        return False
    expected = hmac.new(_CSRF_SECRET, f"{session_id}:{raw}".encode(), hashlib.sha256).hexdigest()[:16]
    return hmac.compare_digest(mac, expected)

# 演示：同会话校验通过，跨会话或篡改则失败
sid = "sess-user42"
tok = issue_csrf_token(sid)
print("verify same session:", verify_csrf_token(tok, sid))
print("verify other session:", verify_csrf_token(tok, "sess-other"))
tampered = tok[:-2] + "ab"
print("verify tampered:", verify_csrf_token(tampered, sid))
assert verify_csrf_token(tok, sid) is True
assert verify_csrf_token(tok, "sess-other") is False
# 预期输出:
# verify same session: True
# verify other session: False
# verify tampered: False
```

```bash
# 前端携带 CSRF 的请求示意
curl -X POST http://localhost:8000/api/tasks \
  -H "Cookie: session=sess-user42" \
  -H "X-CSRF-Token: <csrf_token>" \
  -H "Content-Type: application/json" \
  -d '{"filename":"meeting.wav"}'
```

> **工程启示**：防注入不是“加一个过滤函数”就结束，而是分层职责——输入层做白名单校验，存储层用参数化，输出层做转义；写操作的 CSRF 令牌与 Cookie 的 `SameSite` 配合，才能守住“用户已登录”这一信任边界。

