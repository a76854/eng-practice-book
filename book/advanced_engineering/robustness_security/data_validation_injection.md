---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

# 数据校验与防注入

上一节确认了"谁"在请求，身份可信不等于输入可信。已登录的用户一样可以提交精心构造的关键词，外部搜索回来的标题更是别人写的。本节守住数据的边界：先立起校验与转义的职责分工，再依次看 SQL 注入、XSS 与 CSRF 三种典型攻击面。SQL 注入的原理在讲数据库访问时已经说明（[访问数据库](../../backend_development/persistence_sql_orm/accessing_database.md)），这里不再重跑对照实验，只把它放进分层防御的框架里看位置。

## 校验与转义的分工

数据在两个时刻经过防线：进入系统时，离开系统时。这两道关防的不是同一件事，职责必须分清。

进入系统时做校验，判的是形状与业务规则：关键词不能超过一百个字符，页码必须是正整数，标题不能带控制字符。校验不通过，请求就该被拒绝，返回明确的 4xx，让调用方去改。

离开系统时做转义，判的是"这段内容将进入什么上下文"。内容一旦要拼进 HTML、SQL 或命令行，其中与目标语法同形的字符就必须先被改写，让数据永远只是数据，不会被当成结构的一部分。

| 维度 | 输入校验 | 输出转义 |
| --- | --- | --- |
| 拦截时机 | 数据进入系统时 | 数据进入渲染上下文时 |
| 判断依据 | 形状与业务规则 | 目标语法的特殊字符 |
| 不通过的处理 | 拒绝请求，返回 4xx | 改写为实体，不拒绝 |
| 常见落点 | 路由模型、Service 白名单 | 模板引擎、`html.escape` |
| 常见误区 | 以为校验通过就不必转义 | 以为转义之后就不必校验 |

两张表一句话：校验管"不该进来的"，转义管"出去的不被当代码执行"。一段文本通过校验，只说明它符合业务规则，说明不了它放进 HTML 里安全。

下面这段代码把两层防线各做一次。搜索关键词走校验，外部回来的标题走转义：

```{code-cell} ipython3
import html
import re

CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


def validate_query(raw: str) -> str:
    keyword = raw.strip()
    if not (1 <= len(keyword) <= 100):
        raise ValueError("关键词长度需在 1 到 100 之间")
    if CONTROL_CHARS.search(keyword):
        raise ValueError("关键词含控制字符")
    return keyword


def render_snippet(raw: str) -> str:
    return f"<p>{html.escape(raw, quote=True)}</p>"


print(render_snippet(validate_query("pydantic 校验")))

attack = '<img src=x onerror="alert(1)">'
print(render_snippet(validate_query(attack)))

try:
    validate_query("bad\x01query")
except ValueError as exc:
    print("校验拦截:", exc)
```

恶意标题通过了校验，因为它的长度与字符集都正常，作为文本没有任何问题；真正让它失去杀伤力的是转义，`<` 与 `>` 被改写之后只剩下一段普通文字。这就是两道关必须同时存在的理由。

## SQL 注入

SQL 注入的根因只有一句话：把外部输入拼进了 SQL 语句的结构位置。语句本来应该长成 `WHERE doc_id = ?`，用户输入只填问号；一旦用字符串拼接，输入就有了变成语法的机会。

前面已经用一段对照实验说明过：参数化查询把语句与值分开传输，数据库按值比较，输入再像语法也只是值。本节补充的是它覆盖不到的地方。

```python
# 值的位置可以参数化，标识符的位置不行
safe = "SELECT doc_id FROM favorites WHERE doc_id = ?"
unsafe = f"SELECT doc_id FROM favorites ORDER BY {user_choice}"  # 排序字段不能参数化
```

值和标识符在驱动眼里是两种东西：值可以是任意内容，驱动保证它不被解析；表名、列名、排序方向属于语句结构的一部分，占位符替换不了它们。用户能选排序字段，就得用白名单把有限几个合法取值映射成固定常量，绝不把输入拼进去。

| 出现位置 | 可否参数化 | 做法 |
| --- | --- | --- |
| 条件里的值 | 可以 | 占位符传参，输入只是值 |
| 表名、列名、排序方向 | 不可以 | 白名单映射，命中才用 |
| 数量与长度 | 视驱动 | 先转成整数再传，不传字符串 |

文档查询里能被用户影响的标识符只有排序字段，默认按相关度排，前端允许按时间排序，白名单里就只有两个取值。范围小到可以穷举时，白名单是最省心的防线。

## XSS

跨站脚本发生在"用户提供的内容被当作 HTML 或 JavaScript 原样渲染"的时候。文档查询的攻击面不止一处：搜索关键词会回显在结果页上，外部搜索返回的标题与摘要更是不可控的第三方内容。若前端用 `innerHTML` 或 `v-html` 直接插入，`<script>` 或 `onerror` 这类钩子就会在访问者的浏览器里执行。

这类内容常常被存进数据库，在别的页面、别的时间被渲染出来，因此它比反射型更隐蔽。防线仍然分两层：后端做校验，拦住长度异常与控制字符；渲染层做转义，把 `& < > " '` 改写成实体。Vue 的 `{{ }}` 默认转义，只有 `v-html` 例外，所以这条纪律可以简化成一句话：文档内容一律走默认插值，需要富文本时先经过可信的清洗库。CSP（Content Security Policy）作为第三层，限定页面只能加载同源脚本，即便有内容漏网也多一道闸。

## CSRF

跨站请求伪造利用的是浏览器的自动行为：请求只要发往目标站点，Cookie 就会被自动带上。攻击者在自己的页面上放一个隐藏表单，诱导已登录的用户提交，服务端看到的是合法 Cookie，于是把这次收藏或删除当成用户本人的操作。

防御的关键是把"Cookie 自带的凭证"和"只有本站脚本能拿到的凭证"凑成一对，两者都对才算数。

- **同步令牌**：写操作必须携带 `X-CSRF-Token`，它由服务端签发、与当前会话绑定，攻击者拿不到，也无法伪造。
- **Cookie 属性**：`SameSite=Lax` 或 `Strict` 让跨站请求带不上 Cookie，`HttpOnly` 让脚本读不到 Cookie。
- **来源校验**：校验 `Origin` 或 `Referer` 作为补充，但不能只靠它，部分场景下这两个头会缺失。

令牌生成要用密码学随机数，并且和会话绑定，避免令牌与会话脱节。

```{code-cell} ipython3
import hashlib
import hmac
import secrets

CSRF_SECRET = b"csrf-secret-rotate-in-prod-32bytes"


def issue_csrf_token(session_id: str) -> str:
    nonce = secrets.token_urlsafe(32)
    mac = hmac.new(CSRF_SECRET, f"{session_id}:{nonce}".encode(), hashlib.sha256).hexdigest()[:16]
    return f"{nonce}.{mac}"


def verify_csrf_token(token: str, session_id: str) -> bool:
    try:
        nonce, mac = token.rsplit(".", 1)
    except ValueError:
        return False
    expected = hmac.new(CSRF_SECRET, f"{session_id}:{nonce}".encode(), hashlib.sha256).hexdigest()[:16]
    return hmac.compare_digest(mac, expected)


token = issue_csrf_token("sess-user42")
print("同会话提交:", verify_csrf_token(token, "sess-user42"))
print("换一个会话:", verify_csrf_token(token, "sess-user99"))
print("令牌被改过:", verify_csrf_token(token[:-2] + "ab", "sess-user42"))
```

把会话号混进签名，令牌就只对它所属的会话有效。攻击者能诱导浏览器发出请求，却拿不到这个令牌，服务端一比对就拦下了。

```bash
# 写操作同时带上 Cookie 与 CSRF 令牌
curl -X POST http://localhost:8000/api/favorites \
  -H "Cookie: session=sess-user42" \
  -H "X-CSRF-Token: <csrf_token>" \
  -H "Content-Type: application/json" \
  -d '{"doc_id":"d1"}'
```

## 本节小结

- 校验管数据的形状与规则，进出方向各一道；转义管内容进入渲染上下文后的安全，两者不能互相替代。
- SQL 注入的根因是拼接，参数化让语句与值分离；值可以参数化，标识符不行，只能白名单。
- XSS 的防线是校验加转义，文档内容走默认插值，`v-html` 只在清洗之后使用，CSP 作为第三层。
- CSRF 靠同步令牌与 Cookie 属性配合，令牌用密码学随机数并与会话绑定，来源校验只作补充。
- 三类攻击对应三条不同的边界：数据库访问层、渲染层、会话层，防线落在正确的层才有效。
