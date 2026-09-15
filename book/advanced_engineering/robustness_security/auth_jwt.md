---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

# 认证与授权

学完本节，你能回答：

- 接口开始收费之后，为什么第一件事是能认出“这是谁”
- 服务端会话与令牌各自把状态放在哪，代价分别是什么
- 校验点为什么要收敛在一处，而不是散落在每个处理函数里
- 密码与密钥应该怎么存，为什么它们的存法决定了一次泄露的后果

> 信任之前，先有验证。

上一章讲大模型我们通过API进行了调用，使用了 `API_KEY` 调用大模型API。本节我们也来设想一个场景：

设想你写了一个软件文档检索工具，免费开放，打开网页就能搜。刚上线时一切顺当，用的人多了麻烦就来了：有人写脚本循环调用，一个人吃掉大半带宽和上游额度，正常用户反而搜不动。要治住这件事，只有一条路：给每个使用者一个账号。注册之后，谁用了多少记在谁头上，每人每月 1000 次免费额度，用完为止；将来要给团队开更高额度，或者按量收费，账也从同一个地方出。

那么就印出来一个问题，服务端凭什么相信面前这个请求来自某个具体的用户。

## 从会话到令牌



接口的第一个问题从数据是什么，变成了“这是谁在请求”。搜索本身没变，返回的内容对谁都一样，但服务端必须能把这次请求对应到一个确定的账号：额度扣在谁身上、超限时拦谁、封号封的是谁。让服务端认出用户的办法有两代。

第一代是服务端会话。用户登录后，服务端把身份状态存进内存或 Redis，只把一个 `session_id` 交给浏览器；此后每个请求带上这个编号，服务端拿它回存储里查。这套做法把状态留在自己手上，撤回方便，但是多开一个实例就要共享会话存储，每个请求都要查一次库，跨域与移动端场景下 Cookie 也未必好带。

第二代是令牌。服务端在登录成功时，把"已验证的身份断言"直接签发给客户端；此后客户端每次请求都带着它，服务端只验签，不查存储。令牌一旦签发，在有效期结束前难以单条撤回，过期时间与权限范围必须提前设计好。

| 维度 | 服务端会话 | 令牌 |
| --- | --- | --- |
| 状态放在哪 | 服务端内存或 Redis | 令牌自身，客户端持有 |
| 校验成本 | 每次请求查存储 | 本地验签，不查库 |
| 多实例部署 | 需要共享会话存储 | 各服务各自验签 |
| 主动撤回 | 删除会话立即生效 | 有效期内难以单条撤回 |
| 典型适用 | 单体传统 Web 应用 | 多服务、多端、跨域 |

会话把控制权留在服务端，令牌把状态交给客户端。文档查询要同时服务网页端与移动端，还要让搜索、计费与原文导出拆成不同服务各自校验身份，令牌是更顺手的选择。

## 签发与验签

令牌的签发与校验也有一些库，`PyJWT` 这样的库已经封装好了签名、过期与篡改检测。先跑通一次完整的签发与校验：

```{code-cell} ipython3
import os
import time

import jwt

SECRET = os.getenv("JWT_SECRET", "dev-secret-change-in-prod-32bytes!!")

now = int(time.time())
payload = {"sub": "user42", "plan": "free", "iat": now, "exp": now + 900, "iss": "doc-search"}

token = jwt.encode(payload, SECRET, algorithm="HS256")
print("token:", token[:48] + "...")

decoded = jwt.decode(token, SECRET, algorithms=["HS256"], issuer="doc-search")
print("sub:", decoded["sub"], "plan:", decoded["plan"])

tampered = token[:-3] + "abc"
try:
    jwt.decode(tampered, SECRET, algorithms=["HS256"], issuer="doc-search")
except jwt.InvalidTokenError as exc:
    print("篡改被拒绝:", type(exc).__name__)
```

`jwt.decode` 一次完成了四件事：验签、校验签发方、校验是否过期、把载荷解出来。任何一项不通过都抛异常，调用方不需要自己比较时间戳。

令牌形如 `header.payload.signature`，三段用点分开。`header` 声明签名算法，`payload` 承载断言（`sub` 是谁、`plan` 属于哪个套餐、`exp` 何时过期），`signature` 用密钥对前两段签名，保证内容没被改过。这里有个常见的误解要提前拆掉：载荷只是编码，不是加密，任何人都能解出里面的内容，所以它只能放可公开的断言，不能放密码与密钥。

签名算法有两种常见选择。HS256 用同一个密钥签发与校验，实现简单，密钥必须只留在服务端；RS256 用私钥签发、公钥校验，适合多个服务只验签不签发的场景，公钥可以放心分发。

| 算法 | 密钥 | 签发方 | 适合的场景 |
| --- | --- | --- | --- |
| HS256 | 一对共享密钥 | 任意持有密钥的服务 | 单体或少量服务，部署简单 |
| RS256 | 私钥签发、公钥校验 | 认证服务独占私钥 | 多服务验签，公钥可公开分发 |

`SECRET` 只从环境变量读取，这一条纪律和上一章的 API key 完全一样：密钥不进代码仓库，不写进日志，不返回给前端。密钥一旦泄露，攻击者可以自行签发任意身份的令牌，绕过全部登录流程。

## 服务端校验与授权

签发之后，校验写在哪里是个判断题。如果每个接口都自己解一遍令牌，规则就会散落各处，改一次校验要翻遍所有处理函数。更稳妥的做法是把校验写成依赖，让路由声明"我需要一个已登录用户"，框架负责在进入业务之前拦下不合格的请求。

下面的代码把校验收敛成两个依赖：`current_user` 负责验签并返回身份，`require_plan` 负责判断套餐。搜索接口声明前者，验签通过就可以按账号累计用量；原文接口再声明后者，只有专业版能取到全文。

```{code-cell} ipython3
import os
import time

import jwt
from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.testclient import TestClient

SECRET = os.getenv("JWT_SECRET", "dev-secret-change-in-prod-32bytes!!")
bearer = HTTPBearer(auto_error=False)


def current_user(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> dict:
    if credentials is None:
        raise HTTPException(status_code=401, detail="missing token")
    try:
        return jwt.decode(credentials.credentials, SECRET, algorithms=["HS256"], issuer="doc-search")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="invalid token")


def require_plan(plan: str):
    def dependency(user: dict = Depends(current_user)) -> dict:
        if user.get("plan") != plan:
            raise HTTPException(status_code=403, detail="plan upgrade required")
        return user

    return dependency


app = FastAPI()


@app.get("/api/search")
def search(q: str, user: dict = Depends(current_user)) -> dict:
    # 验签通过后，这一行就可以按 user["sub"] 记一次用量
    return {"query": q, "account": user["sub"], "results": []}


@app.get("/api/documents/{doc_id}/fulltext")
def fulltext(doc_id: str, user: dict = Depends(require_plan("pro"))) -> dict:
    return {"doc_id": doc_id, "account": user["sub"], "content": "..."}

client = TestClient(app)

def make_token(plan: str) -> str:
    now = int(time.time())
    payload = {"sub": "user42", "plan": plan, "iat": now, "exp": now + 900, "iss": "doc-search"}
    return jwt.encode(payload, SECRET, algorithm="HS256")

free = {"Authorization": f"Bearer {make_token('free')}"}
pro = {"Authorization": f"Bearer {make_token('pro')}"}

print("已登录搜索:", client.get("/api/search", params={"q": "pydantic"}, headers=free).status_code)
print("免费账号看原文:", client.get("/api/documents/d1/fulltext", headers=free).status_code)
print("专业账号看原文:", client.get("/api/documents/d1/fulltext", headers=pro).status_code)
print("没有令牌:", client.get("/api/search", params={"q": "pydantic"}).status_code)
```

四种结局覆盖了三层判断：已登录的搜索返回 200，免费账号访问原文返回 403，专业账号访问原文返回 200，没有令牌在进入业务之前就返回 401。401 表示"你是谁还不知道"，403 表示"知道你是谁，但你的套餐不够"，两个状态码的语义不要混用。

授权要在验签之后做。`plan` 取自已经验签的载荷，此时内容可信，判断套餐不必再查一次库。代价是套餐在令牌有效期内被冻结：用户刚升级到专业版，手里的旧令牌仍写着免费，得等它过期或换发新令牌才生效，这正是下一小节要处理的问题。粒度按需要定：搜索对已注册用户开放，按次数记到 `sub` 上扣额度；原文访问按套餐放行；管理员接口再多一层身份判断。这些差别都只是载荷里的一个字段。

## 令牌生命周期

令牌的有效期是一场拉锯，在收费产品里这场拉锯更值钱。有效期越长，用户越省事，泄露之后被刷掉的额度也越多；越短越安全，用户却要不停重新登录。常见的折中是两种令牌分工。

| 令牌 | 有效期 | 用途 | 能否撤回 |
| --- | --- | --- | --- |
| 访问令牌 | 15 分钟左右 | 随每个请求携带，直接换取资源 | 不能，靠短有效期把窗口压小 |
| 刷新令牌 | 7 天左右 | 单独接口换取新的访问令牌 | 能，存进库，删除即失效 |

访问令牌短，泄露的窗口就短；刷新令牌长，但只在刷新接口使用，并且服务端存有一份记录，可以按条作废。用户改密码、退订或触发风控时，把该用户的刷新令牌记录删掉，访问令牌最多再撑十五分钟。若要求"封号后立即踢掉所有令牌"，还有一处可以下手：在用户表存一个版本号，签发时写进载荷，校验时比对版本，改密就加一，所有旧令牌当场失效。这个方案每次验签不需要查库，代价是版本号要随用户信息一起带上，具体权衡见章末思考题。

## 密码与密钥的存放

前面讲的是凭证怎么发，还有一半是凭证怎么存。账号一旦绑定付费，数据库泄露的代价就不只是密码本身，还有用户对这家产品的信任。

明文存储是底线之下的做法，一旦泄露，用户的密码连同他在其他网站的账号一起沦陷。用一次哈希也不行：同样的密码算出同样的摘要，攻击者拿一张预先算好的对照表就能反查，普通密码的空间太小，穷举并不贵。正确的做法是慢哈希加盐：给每个用户生成一段随机盐，和密码一起参与计算；盐保证相同密码得到不同摘要，逐用户对表格失效；慢哈希故意让每次计算变贵，把穷举的成本抬到攻击者不愿承担的高度。

```{code-cell} ipython3
import hashlib
import hmac
import os

PARAMS = {"n": 2**14, "r": 8, "p": 1}

def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, dklen=32, **PARAMS)
    return f"scrypt${PARAMS['n']}${salt.hex()}${digest.hex()}"

def verify_password(password: str, stored: str) -> bool:
    _, _, salt_hex, digest_hex = stored.split("$")
    digest = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt_hex), dklen=32, **PARAMS)
    return hmac.compare_digest(digest.hex(), digest_hex)

stored = hash_password("correct-horse-battery")
print("存储格式:", stored[:28] + "...")
print("密码正确:", verify_password("correct-horse-battery", stored))
print("密码错误:", verify_password("wrong-horse-battery", stored))
```

这段代码演示了三件事：盐随用户随机生成并跟摘要一起存；校验用同样的参数重算并做恒定时间比较；存储串里带上参数，将来调高成本时老密码仍然能校验。比较用 `hmac.compare_digest` 而不是 `==`，是为了避免比较耗时随匹配长度变化而泄露信息。标准库之外，`bcrypt`、`argon2` 这类专门的密码库做了同样的设计，生产里直接用它们即可。

密钥的纪律和密码不同，却指向同一条原则：不在明文通道之外的地方多留一份。

| 存放位置 | 是否可接受 | 说明 |
| --- | --- | --- |
| 写进代码并提交仓库 | 不可接受 | 历史记录里删不干净，等同公开 |
| 本地 `.env` 文件 | 本地开发可接受 | 必须进 `.gitignore`，不进版本库 |
| CI 的 secrets、部署环境变量 | 生产可接受 | 权限收敛在仓库与平台，可审计 |
| 密钥管理服务加定期轮换 | 更稳妥 | 轮换时新旧密钥并存一段时间 |

轮换是密钥管理里最容易忽略的一步。任何密钥都有更换的一天，JWT 的密钥更是如此：更换时若立刻停用旧密钥，所有已签发的令牌会当场失效，用户集体掉线。可行做法是同时接受新旧两个密钥，等旧令牌自然过期之后再彻底停用。

## 本节小结

- 会话把状态留在服务端，撤回方便但每次请求查库；令牌把状态交给客户端，验签便宜但有效期内难以单条撤回。
- 签发与校验交给库完成，校验点收敛成依赖，路由只声明“需要已登录用户”或“需要某个套餐”，401 与 403 的语义不混用。
- 访问令牌短、刷新令牌长且可作废，两者分工是可用性与安全性的折中；改密、退订或封号踢人靠令牌版本号或刷新令牌表。
- 密码用慢哈希加盐存储，盐逐用户随机，比较用恒定时间函数；密钥只放环境变量或密钥管理服务，绝不进代码与日志。