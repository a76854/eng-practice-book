---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

# 综合实战

学完本节，你能回答：

- 一个注册请求从进入到返回，依次穿过哪几层，每一层各自做什么？
- Service 层除了查重，为什么密码不能明文落库，密码哈希怎么做才安全？
- 分层之后，Controller 如何把业务错误映射成正确的 HTTP 状态码？
- 为什么数据访问要放进 Repository，而不是让 Controller 直接写 SQL？

> 一个注册请求像一张快递单：从前台签收，交业务室核验、登记，再送库房归档，最后把回执寄回。每一站只干本分的事，单子才能在站点之间顺畅流转，出了错也能一眼看出卡在哪一站。

前四章各自交付了一件工具：第 3 章给了FastAPI框架以及分层组织方式，第 4 章给了 HTTP 的契约与状态码，第 5 章给了持久化与 SQL，第 6 章给了性能优化视角。为了增强几个章节的连贯性，让读者体会到本章的用意。本节用一个用户注册接口，把"后端框架、HTTP、持久化"串成一条完整链路，看 `POST /users/register` 请求如何穿过框架，最后带着 201 或错误码返回。

```{mermaid}
flowchart LR
    A["HTTP 请求<br/>POST /users/register"] --> C["路由层 Controller<br/>解析参数、映射状态码"]
    C --> S["服务层 Service<br/>校验、查重、密码哈希"]
    S --> R["存储层 Repository<br/>参数化写库"]
    R --> E["HTTP 响应<br/>201 / 400 / 409"]
```

## 定义数据模型与接口

分层的第一步是把边界画清楚。数据在程序里的形态是一个 `User`，存储层对外只承诺三个方法：写入一个用户、按用户名查询、判断用户名是否已存在。至于背后是内存字典还是数据库，调用方不关心。

```{code-cell} ipython3
from dataclasses import dataclass
from typing import Optional, Protocol

@dataclass
class User:
    id: str
    username: str
    password_hash: str

class UserRepository(Protocol):
    def create(self, user: User) -> None: ...
    def get_by_username(self, username: str) -> Optional[User]: ...
    def username_exists(self, username: str) -> bool: ...

print("model ready:", User.__name__)
```

模型与接口就位。注意 `User` 里存的是 `password_hash`，不是明文密码，这个字段名本身就是一层约束，提醒每一层都不该碰明文。

## Repository 层：把数据写进真实数据库

这一层是持久化的落地点，用标准库 `sqlite3` 实现。与第 5 章一致，写库用参数化占位符而不是字符串拼接，用户名上挂 `UNIQUE` 约束，把"不重复"从业务规则变成数据库层面的门卫。连接上加了 `check_same_thread=False`：同步路由会被 FastAPI 丢进线程池执行，而连接对象默认绑定创建它的线程，放开这个限制才能跨线程使用，这正是第 6 章会面对的线程细节。

```{code-cell} ipython3
import sqlite3

class SqliteUserRepository:
    def __init__(self, path: str = ":memory:") -> None:
        self._conn = sqlite3.connect(path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute(
            "CREATE TABLE IF NOT EXISTS users ("
            " id TEXT PRIMARY KEY,"
            " username TEXT NOT NULL UNIQUE,"
            " password_hash TEXT NOT NULL"
            ")"
        )
        self._conn.commit()

    def create(self, user: User) -> None:
        self._conn.execute(
            "INSERT INTO users (id, username, password_hash) VALUES (?, ?, ?)",
            (user.id, user.username, user.password_hash),
        )
        self._conn.commit()

    def get_by_username(self, username: str) -> Optional[User]:
        row = self._conn.execute(
            "SELECT id, username, password_hash FROM users WHERE username = ?", (username,)
        ).fetchone()
        if row is None:
            return None
        return User(id=row["id"], username=row["username"], password_hash=row["password_hash"])

    def username_exists(self, username: str) -> bool:
        row = self._conn.execute("SELECT 1 FROM users WHERE username = ?", (username,)).fetchone()
        return row is not None

repo = SqliteUserRepository()
print("repository ready:", type(repo).__name__)
assert repo.username_exists("alice") is False
```

存储层就绪，初始为空。值得留意的是 `UNIQUE` 约束：即使上层的 Service 查过重，两个并发请求仍可能同时通过查重，这时数据库的 `UNIQUE` 是最后一道防线，撞上时 `INSERT` 抛出 `IntegrityError`。这正是第 6 章讲的竞态，靠底层约束兜底，而非只靠应用层判断。

## Service 层：校验、查重与密码哈希

这一层承载业务规则，不感知 HTTP，通过抛 `ValueError` 表达"哪里不合法"。密码不能明文落库，对它的处理是加盐哈希：每个密码一个随机盐，用 `pbkdf2_hmac` 做单向密钥派生，库里的字段是"盐加哈希"，反向推不出原文。

```{code-cell} ipython3
import hashlib
import secrets

def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), bytes.fromhex(salt), 100_000)
    return f"{salt}${digest.hex()}"

class UserService:
    def __init__(self, repo: UserRepository) -> None:
        self.repo = repo

    def register(self, username: str, password: str) -> User:
        if not username.strip():
            raise ValueError("用户名不能为空")
        if len(password) < 8:
            raise ValueError("密码长度至少 8 位")
        if self.repo.username_exists(username):
            raise ValueError("用户名已注册")
        user = User(
            id=secrets.token_hex(8),
            username=username,
            password_hash=hash_password(password),
        )
        self.repo.create(user)
        return user

service = UserService(repo)

u = service.register("alice", "correct-horse-1")
print("注册成功:", u.username, "id", u.id[:8])
print("存储的密码字段:", u.password_hash[:24], "...")
assert "correct-horse-1" not in u.password_hash
assert u.password_hash.count("$") == 1

try:
    service.register("alice", "another-pass-1")
except ValueError as e:
    print("重复用户名:", e)

try:
    service.register("", "whatever-1")
except ValueError as e:
    print("空用户名:", e)

try:
    service.register("bob", "short")
except ValueError as e:
    print("密码过短:", e)
```

Service 层不 import 任何 HTTP 或数据库模块，只面对 `UserRepository` 接口。规校验、查重、哈希三件事都落在这里，Controller 与 Repository 各司其职。

## Controller 层：路由与状态码

最上面的这一层只做 HTTP 翻译：接收 Pydantic 校验过的输入，调用 Service，把业务错误映射成状态码。这里有一条边界分工值得看清楚：Pydantic 管的是形状，参数有没有、什么类型、超不超长度，越界直接回 422；Service 管的是业务规则，密码够不够强、用户名重不重复，违规回 400 或 409。创建成功回 201，正是第 4 章"状态码表达责任归属"的那句话。

```{code-cell} ipython3
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import BaseModel, Field

class RegisterIn(BaseModel):
    username: str = Field(min_length=1, max_length=64, description="用户名")
    password: str = Field(min_length=1, max_length=128, description="密码")

class UserOut(BaseModel):
    id: str
    username: str

repo2 = SqliteUserRepository()
service2 = UserService(repo2)

app = FastAPI(title="Users API")

@app.post("/users/register", response_model=UserOut, status_code=201)
def register(payload: RegisterIn):
    try:
        user = service2.register(payload.username, payload.password)
    except ValueError as e:
        detail = str(e)
        if "已注册" in detail:
            raise HTTPException(status_code=409, detail=detail)
        raise HTTPException(status_code=400, detail=detail)
    return UserOut(id=user.id, username=user.username)

print("routes:", [r.path for r in app.routes if getattr(r, "path", "").startswith("/users")])
```

路由函数只有一句 try/except 和一次 Service 调用，又薄又清晰。它不碰数据库、不写业务规则，只负责把 HTTP 的进出翻译好。

## 一个请求的完整往返

最后用 TestClient 走一遍完整链路，再从数据库里确认落库的是哈希而非明文。

```{code-cell} ipython3
client = TestClient(app)

r1 = client.post("/users/register", json={"username": "alice", "password": "correct-horse-1"})
print("注册成功:", r1.status_code, r1.json())
assert r1.status_code == 201

r2 = client.post("/users/register", json={"username": "alice", "password": "another-pass-1"})
print("重复用户名:", r2.status_code, r2.json()["detail"])
assert r2.status_code == 409

r3 = client.post("/users/register", json={"username": "bob", "password": "short"})
print("密码过短:", r3.status_code)
assert r3.status_code == 400

stored = repo2.get_by_username("alice")
assert stored is not None
print("库中密码字段:", stored.password_hash[:24], "...")
assert "correct-horse-1" not in stored.password_hash
assert stored.password_hash.count("$") == 1
```

一个 `POST /users/register` 从 TestClient 发出，经路由层翻译、服务层核验、存储层写库，最终带着状态码回到调用方；而数据库里留下的，只有加盐后的哈希。

## 朝花夕拾

| 章节 | 这一节用到了什么 |
|---|---|
| 第3章 分层 | Controller 薄、Service 厚、Repository 藏，单向依赖，替换与测试沿边界进行 |
| 第4章 HTTP | POST 表达创建，状态码表达责任（201 成功、400 校验失败、409 冲突） |
| 第5章 持久化 | 参数化 SQL 防注入，`UNIQUE` 约束在库层兜底，密码哈希与盐 |
| 第6章 并发 | 同步路由交给 FastAPI 走线程池，避免阻塞事件循环；并发查重靠库约束兜底 |