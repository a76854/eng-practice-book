---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

## 本章小结

- **身份边界靠验签守住**：会话把状态留在服务端，令牌把状态交给客户端，两种取舍对应不同的部署形态；校验点收敛成依赖，权限判断只发生在已验签的载荷上；访问令牌短、刷新令牌长且可作废；密码用慢哈希加盐存储，密钥只放环境变量或密钥管理服务。
- **数据边界分两道关**：校验管数据的形状与业务规则，进出方向各一道；转义管内容进入渲染上下文后的安全，两者不能互相替代。SQL 注入靠参数化根治，标识符只能白名单；XSS 靠校验加转义并以 CSP 兜底；CSRF 靠同步令牌与 Cookie 属性配合。
- **依赖边界把故障关进笼子**：捕获放在与外部打交道的仓库层，接住之后先分类再脱敏；重试必须有界并带退避，前提是操作幂等；主路径不可用时给出次优结果，并用 `degraded` 与来源字段把降级的成色说清楚。
- **追溯边界让故障有据可查**：结构化 JSON 字段、分级、按 `request_id` 哈希采样、写入端脱敏，四件事缺一不可；字段先立住，规模小时用 `grep`，规模大了再接入采集、索引与呈现的集中式方案，并把检索升级为告警。
- **四道边界合成一条底线**：身份说明"谁"，数据说明"可不可信"，依赖说明"坏了怎么办"，日志说明"怎么看"，它们共同把"主路径能跑"提升为"在坏的情况下也可预期"，下一章的部署与持续集成就建立在这条底线之上。

## 思考题

1. **令牌撤回**：无状态令牌难以单条撤回，短有效期与刷新轮转让窗口变得有限。若要求"用户改密后立即踢掉所有已签发令牌"，用令牌版本号与每次验签查库两种做法各自的代价是什么？在什么规模下会选后者？
2. **签名算法的选择**：HS256 用共享密钥签发与校验，RS256 用私钥签发、公钥校验。多服务验签场景下，两者的密钥分发与轮换差别在哪？轮换期间如何让新旧密钥并存校验，而不让已签发的令牌集体失效？
3. **校验与转义的归属**：为什么"输入校验通过"不能替代"输出转义"？在文档查询里，搜索关键词与外部返回的标题这两类数据，校验策略与转义策略应有何不同？
4. **参数化的边界**：占位符能防住值的注入，但表名、列名与排序方向无法参数化。若允许用户选择排序字段，白名单该如何设计与维护，才能既不遗漏合法取值，又不至于每加一个字段就改一次代码？
5. **密码哈希的成本**：慢哈希加盐把穷举成本抬高，也把每次登录的开销抬高。请判断参数该怎样选，配合什么限流策略，才能让正常用户几乎无感，而攻击者的成本高到不愿尝试。
6. **日志的噪声与成本**：全量 `INFO` 在高并发下带来存储与费用压力，采样虽能降本却可能丢掉关键失败。结合 `request_id` 哈希采样，说明如何保证同一请求的日志同进同出，同时不丢 `ERROR` 与降级事件。
7. **脱敏与排障的矛盾**：日志脱敏保护了密钥与个人信息，却让排障时的原文不再随手可得。请设计一套分级脱敏与受控访问方案，说明谁在什么条件下可以看到哪一级内容，以及事后如何审计这次查看。
8. **重试的副作用**：对非幂等的写操作直接重试会产生重复记录，文档查询的收藏接口靠主键拒绝了重复。请分析在什么样的事务边界与去重策略下，重试才是安全的，以及重试次数与退避上限应该依据什么确定。
9. **降级的诚实性**：缓存回退提升了可用性，却可能让用户以为看到的是最新结果。请为搜索结果页设计降级提示的文案与呈现方式，说明如何让用户察觉得到，又不至于引起不必要的恐慌。
10. **端到端演练**：为"搜索、收藏、摘要"三段各注入一次故障：关键词校验失败、外部搜索超时、摘要接口限流。请推演日志、告警、重试与降级如何协同，并说明要把一次故障的定位时间压到分钟级，哪些字段与索引是必须提前准备的。

本章把四道边界串成一个闭环：校验过的输入、可信的身份、有界的重试、可感知的降级、可检索的日志。下面用一段代码把它们连起来跑一次，不依赖任何外部服务：

```{code-cell} ipython3
import hashlib
import html
import io
import logging
import os
import time

import jwt

SECRET = os.getenv("JWT_SECRET", "dev-secret-change-in-prod-32bytes!!")


def require_keyword(raw: str) -> str:
    keyword = raw.strip()
    if not (1 <= len(keyword) <= 100):
        raise ValueError("关键词长度非法")
    return keyword


def render_snippet(raw: str) -> str:
    return f"<p>{html.escape(raw, quote=True)}</p>"


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, dklen=32, n=2**14, r=8, p=1)
    return f"scrypt${salt.hex()}${digest.hex()}"


def issue_token(sub: str) -> str:
    now = int(time.time())
    payload = {"sub": sub, "roles": ["user"], "iat": now, "exp": now + 900, "iss": "doc-search"}
    return jwt.encode(payload, SECRET, algorithm="HS256")


def search_with_fallback(query: str, fetch, cache: dict[str, list[str]]) -> dict:
    try:
        results = fetch(query)
        cache[query] = results
        return {"results": results, "degraded": False}
    except TimeoutError as exc:
        if query in cache:
            return {"results": cache[query], "degraded": True, "reason": str(exc)}
        return {"results": [], "degraded": True, "reason": str(exc)}


def healthy_search(query: str) -> list[str]:
    return [f"doc-for-{query}"]


def broken_search(query: str) -> list[str]:
    raise TimeoutError("search timeout")


buf = io.StringIO()
handler = logging.StreamHandler(buf)
handler.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
logger = logging.getLogger("doc_search.summary")
logger.setLevel(logging.INFO)
logger.handlers.clear()
logger.addHandler(handler)
logger.propagate = False

cache: dict[str, list[str]] = {}

print("转义后:", render_snippet(require_keyword('<b>pydantic</b> 校验')))
print("同一密码两次哈希不同:", hash_password("correct-horse") != hash_password("correct-horse"))

decoded = jwt.decode(issue_token("user42"), SECRET, algorithms=["HS256"], issuer="doc-search")
print("令牌身份:", decoded["sub"], "角色:", decoded["roles"])

normal = search_with_fallback("pydantic", healthy_search, cache)
degraded = search_with_fallback("pydantic", broken_search, cache)
logger.info("搜索结束 degraded=%s source=%s", degraded["degraded"], "cache" if degraded["results"] else "empty")
print("正常:", normal["degraded"], "降级:", degraded["degraded"])
print("日志:", buf.getvalue().strip())
```