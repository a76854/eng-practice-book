---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

# 认证与授权 JWT

> 学完本节，你能用 `PyJWT` 签发与校验令牌，用 `Depends(verify_token)` 保护 FastAPI 路由，并说清 `Authorization: Bearer` 的传递与 `exp` 过期的校验点。

## 从会话到令牌：为什么需要无状态

传统的服务端会话把用户状态存在内存或 Redis，浏览器只持有一个 `session_id`。多实例、跨域与移动端场景下，这要求服务端有状态、跨服务共享存储、每次请求查库。

JWT 把“已验证的身份断言”直接签发给客户端，服务端只做验签，不存会话。代价是令牌一旦签发就难以单条撤回，过期与权限必须前置设计。MeetingToText 对外提供 `POST /api/tasks` 与 `GET /api/tasks/{id}` 时，用 JWT 即可让网关与业务服务各自验签，无需共享会话存储。

类比：session 像“寄存手牌”，每次取物都要回柜台查询；JWT 像“盖章门票”，检票员只验章，不查存根。

## 先动手：10 行签发与验签

别先背内部的编码与签名细节，先用库把登录签发和验签跑通。

```{code-cell} ipython3
import os, time, jwt

# 密钥只从环境变量读取，绝不写进代码或返回给前端
# 本地开发在 .env 中配置：JWT_SECRET=dev-secret-change-in-prod-32bytes!!
SECRET = os.getenv("JWT_SECRET", "dev-secret-change-in-prod-32bytes!!")

now = int(time.time())
payload = {"sub": "user42", "roles": ["user"], "iat": now, "exp": now + 3600, "iss": "m2t"}

# 签发：登录成功后返回给客户端
token = jwt.encode(payload, SECRET, algorithm="HS256")
print("token:", token[:48] + "...")

# 验签：网关或业务服务收到请求时校验
decoded = jwt.decode(token, SECRET, algorithms=["HS256"], issuer="m2t")
print("decoded sub:", decoded["sub"], "roles:", decoded["roles"])

# 过期与篡改由库统一抛异常，无需手写比较
bad_token = token[:-3] + "abc"
try:
    jwt.decode(bad_token, SECRET, algorithms=["HS256"])
except jwt.InvalidSignatureError as e:
    print("invalid signature detected:", e)
except jwt.InvalidTokenError as e:
    print("invalid token:", e)

assert decoded["sub"] == "user42"
```

> **环境约定**：本书面向 Linux，`exp` / `iat` 统一用 UTC 的 Unix 秒（`time.time()`），避免本地时区差异。有效期校验由服务端用 `jwt.decode` 自动完成，不信任客户端时钟。

JWT 形如 `header.payload.signature`，三段以点分隔。`header` 声明算法，`payload` 承载断言（`sub`、`exp`、`roles` 等，注意载荷只是编码，不是加密），`signature` 由库用密钥对前两段做签名，保证内容未被篡改且由持有密钥的服务端签发。上面 10 行已覆盖“签发、验签、过期、篡改检测”的完整闭环。

> **安全前提**：HS256 的密钥必须足够长且仅存于服务端环境变量或密钥管理服务；多服务验签可改用 RS256，私钥留服务端，公钥分发给验签方。

## 服务端校验：Depends 与 Authorization Bearer

权限校验点应放在业务边界——FastAPI 的依赖或网关中间件，而不是散落在每个 handler 内部。客户端按 `Authorization: Bearer <token>` 携带令牌，服务端用 `Depends` 统一验签。

```{code-cell} ipython3
import os, time, jwt
from fastapi import FastAPI, Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.testclient import TestClient

SECRET = os.getenv("JWT_SECRET", "dev-secret-change-in-prod-32bytes!!")
security = HTTPBearer()

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    token = credentials.credentials
    try:
        return jwt.decode(token, SECRET, algorithms=["HS256"], issuer="m2t")
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="invalid token")

app = FastAPI()

@app.get("/api/tasks")
def list_tasks(user=Depends(verify_token)):
    # 验签通过后，user 即为可信身份断言
    if "user" not in user.get("roles", []):
        raise HTTPException(status_code=403, detail="forbidden")
    return {"sub": user["sub"], "tasks": []}

# --- 可执行校验：签发一个令牌并携带 Bearer 访问 ---
now = int(time.time())
token = jwt.encode({"sub": "user42", "roles": ["user"], "iat": now, "exp": now + 3600, "iss": "m2t"}, SECRET, algorithm="HS256")
client = TestClient(app)

ok = client.get("/api/tasks", headers={"Authorization": f"Bearer {token}"})
print("authorized:", ok.status_code, ok.json())

no_token = client.get("/api/tasks")
print("no token:", no_token.status_code)

bad = client.get("/api/tasks", headers={"Authorization": "Bearer bad.bad.bad"})
print("bad token:", bad.status_code)

assert ok.status_code == 200
assert no_token.status_code in (401, 403)  # HTTPBearer 无令牌时返回 401/403
assert bad.status_code == 401
```

要点只有三处：`SECRET` 来自 `.env`、 `jwt.encode` / `jwt.decode` 由库完成签名与校验、`Depends(verify_token)` 收敛所有路由的鉴权逻辑。

```bash
# .env 配置示例（加入 .gitignore，绝不提交）
echo 'JWT_SECRET=dev-secret-change-in-prod-32bytes!!' >> .env

# 携带 JWT 的请求示意
curl -H "Authorization: Bearer <access_token>" http://localhost:8000/api/tasks
```

## 令牌过期与 RBAC：校验点放在哪里

短有效期是 JWT 的核心约束。常见做法是访问令牌设为 15 分钟，随每个请求携带；刷新令牌设为 7 天，仅用于换取新访问令牌并可做撤回表。生产中用“短 access + 可撤回 refresh + 关键操作二次校验”来平衡无状态与可撤回的矛盾，本节不展开轮转代码，聚焦可用形态。

RBAC 在验签之后做：从 `payload.roles` 取角色，按路由要求的最小角色集合做包含判断。

```{code-cell} ipython3
import os, time, jwt

SECRET = os.getenv("JWT_SECRET", "dev-secret-change-in-prod-32bytes!!")

def has_role(token: str, required: str) -> bool:
    data = jwt.decode(token, SECRET, algorithms=["HS256"], issuer="m2t")
    return required in data.get("roles", [])

now = int(time.time())
editor_token = jwt.encode(
    {"sub": "user42", "roles": ["user", "editor"], "iat": now, "exp": now + 900, "iss": "m2t"},
    SECRET, algorithm="HS256",
)
print("editor:", has_role(editor_token, "editor"))
print("admin:", has_role(editor_token, "admin"))

assert has_role(editor_token, "user") is True
assert has_role(editor_token, "admin") is False
print("RBAC 校验通过：roles 来自已验签的 payload，在 Depends 之后判断")
```

> **工程启示**：JWT 的优势是无状态验签，代价是撤回困难。用库而非手写加密，用 `Depends` 收敛校验点，用 `Authorization: Bearer` 统一传递，用 `exp` 控制窗口，权限判断只在已验签的 `payload` 上做。
