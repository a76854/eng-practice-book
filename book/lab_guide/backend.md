---
numbering: false
---

# 实验三 文档查询后端

本实验对应理论 [第 3 章 后端开发概览](../backend_development/backend_essence/index.md)、[第 4 章 HTTP 与 RESTful](../backend_development/http_restful/index.md)、[第 5 章 数据持久化](../backend_development/persistence_sql_orm/index.md) 与 [第 7 章 综合实战](../backend_development/backend_synthesis/index.md)，并在末尾用 [第 12 章 认证与授权](../advanced_engineering/robustness_security/auth_jwt.md) 的最小实现收口。建议先通读 [FastAPI 与分层架构](../backend_development/backend_essence/fastapi_and_layered_architecture.md)、[HTTP 与 RESTful](../backend_development/http_restful/http_and_restful.md) 与 [ORM](../backend_development/persistence_sql_orm/orm.md)，再动手。

本实验不提供起始代码，你将从零建立一个后端服务，并在五个任务中逐层长出完整能力。

## 实验目标

通过完成文档查询后端，你将：

1. **组织三层架构**：用 Controller、Service、Repository 三层组织 FastAPI 服务，并用 Protocol 把两种数据来源抽象成可替换的接口。
2. **落地 REST 契约**：按 RESTful 约定实现搜索与收藏接口，让方法与状态码符合语义，并用 Pydantic 声明请求与响应契约。
3. **完成持久化与迁移**：用 SQLite 保存收藏，并用版本化迁移管理表结构演进，做到可升级、可回滚。
4. **贯通完整链路**：用一个请求贯穿三层的契约测试验证整条链路，并说清每一层的职责边界。
5. **加上最小认证**：用 JWT 完成一次最小可用的登录与令牌校验，使受保护接口对未授权请求返回 401。

## 背景故事

你和同学在做一个文档检索工具。用户在搜索框里输入关键词，后端去外部检索服务拿到网页文档，整理后返回给用户；为了防滥用，工具要求先注册账号再使用；用户还能把感兴趣的文档加入收藏，下次直接查看。

团队已经定好了技术栈：后端用 FastAPI，前端随后接入。本实验只做后端，等这一步站稳，实验四再做前端，实验五再接入大模型与缓存，实验六把整套应用容器化交付。

## 预备知识

**核心数据模型**

- `Document(id, title, source, url, content)`：一条检索结果，`id` 用文档 URL，`source` 取域名的顶级部分。
- `Favorite(doc_id, created_at)`：一条收藏，`doc_id` 引用 `Document.id`。

**接口约定**

| 方法 | 路径 | 说明 | 成功 | 失败 |
|------|------|------|------|------|
| GET | `/api/health` | 健康检查 | 200 | — |
| GET | `/api/search?q=` | 按关键词检索文档 | 200（列表） | — |
| POST | `/api/favorites` | 收藏一篇文档 | 201 | 409 重复 |
| GET | `/api/favorites` | 列出已收藏 | 200（列表） | — |
| DELETE | `/api/favorites/{doc_id}` | 取消收藏 | 204 | 404 不存在 |
| POST | `/api/login` | 登录换取令牌 | 200（含 `token`） | 401 凭证错误 |

**状态码约定**

| 状态码 | 含义 |
|--------|------|
| 200 | 查询成功 |
| 201 | 创建成功 |
| 204 | 删除成功，无响应体 |
| 401 | 未认证或令牌无效 |
| 404 | 资源不存在 |
| 409 | 与现有资源冲突（重复收藏） |
| 422 | 请求体校验失败（由 FastAPI 自动返回） |

**目录约定**

```
src/docsearch/
├── __init__.py
├── api/            # Controller 层：路由、参数解析、状态码映射
├── service/        # Service 层：业务规则，不感知 HTTP
└── repository/     # Repository 层：数据来源，两个协议与实现
tests/              # pytest 测试
pyproject.toml      # 依赖与工具配置
```

**环境约定**

- 用 `uv` 管理依赖与项目元数据，在书仓根目录的 `.venv` 环境中运行。
- 外部检索未配置 `WEBSEARCH_API_KEY` 时返回空列表，保证无网络也能演示。
- 认证只需要最小可用，用 JWT 完成登录与校验即可。

---

# 任务一：搭建三层骨架

## 任务目标

建立三层目录结构，定义两个仓储协议与它们的实现，让各层依赖方向清晰。

## 需求

1. 用 `dataclass` 定义 `Document`，字段为 `id`、`title`、`source`、`url`、`content`。
2. 定义两个协议（`typing.Protocol`）：
   - `DocumentRepository`：`search(query: str) -> list[Document]`
   - `FavoriteRepository`：`add(doc_id)`、`remove(doc_id)`、`list_all()`、`exists(doc_id)`
3. 提供两个实现：
   - `WebSearchRepository`：调用外部检索服务，把结果整理成 `Document`；未配置 key 时返回空列表。
   - `SqliteFavoriteRepository`：用标准库 `sqlite3` 实现，`doc_id` 作为主键。
4. `Service` 通过构造参数接收两个仓储，不在内部 `new` 具体实现。
5. 保持依赖方向：`service` 不导入 `fastapi`，`api` 不直接执行 SQL。

## 验收标准

| 验收项 | 具体要求 |
|--------|----------|
| 目录结构 | `src/docsearch/` 下存在 `api`、`service`、`repository` 三层 |
| 协议抽象 | 两个 `Protocol` 定义完整，实现类可被替换而不改业务代码 |
| 依赖注入 | `Service` 通过构造接收仓储依赖 |
| 边界清晰 | `service` 不导入 Web 框架，`api` 不含 SQL |

## 提交要求

```bash
git switch -c exp/01-layers
git add src/ pyproject.toml
git commit -m "feat: scaffold three-layer structure with repository protocols"
git push -u origin exp/01-layers
```

---

# 任务二：实现 REST 契约

## 任务目标

按接口约定实现搜索与收藏端点，用 Pydantic 声明契约，并用 `TestClient` 验证。

## 需求

1. 按上面的接口约定实现全部端点，方法与路径一致。
2. 用 Pydantic 定义请求体与响应模型，例如 `FavoriteIn`、`DocOut`、`TokenOut`。
3. 状态码符合约定：创建返回 201，删除返回 204，重复收藏返回 409，不存在返回 404。
4. 非法请求体交给 FastAPI 自动返回 422，错误细节可读。
5. 用 `TestClient` 为每个端点写测试，覆盖正常路径与至少一个错误路径。

## 验收标准

| 验收项 | 具体要求 |
|--------|----------|
| 端点齐全 | 约定表中的端点全部实现 |
| 状态码正确 | 201 / 204 / 404 / 409 语义正确 |
| 契约模型 | 请求与响应由 Pydantic 模型声明，非法输入返回 422 |
| 测试覆盖 | `TestClient` 覆盖正常与错误路径，测试通过 |

## 提交要求

```bash
git switch -c exp/02-rest-contract
git add src/ tests/
git commit -m "feat: implement search and favorites endpoints with contracts"
git push -u origin exp/02-rest-contract
```

---

# 任务三：持久化与迁移

## 任务目标

让收藏真正落库，并用版本化迁移管理一次表结构演进。

## 需求

1. 收藏写入 SQLite 文件，`doc_id` 作为主键，插入使用参数化占位符。
2. 引入版本化迁移：至少演示一次表结构演进，例如给 `favorites` 增加 `status` 或 `created_at` 列。
3. 提供升级与回滚两条路径，可用手写 `schema_version` 表配 SQL 脚本，也可用 Alembic。
4. 迁移脚本可重放、可回滚，业务代码不直接手改表结构。

## 验收标准

| 验收项 | 具体要求 |
|--------|----------|
| 落库可验 | 收藏写入 SQLite，重启服务后仍可查回 |
| 主键约束 | 同一 `doc_id` 重复收藏由数据库层兜底 |
| 迁移可升级 | 能演示一次加列演进并有版本记录 |
| 迁移可回滚 | 能回滚到演进前的结构，数据不丢失 |

## 提交要求

```bash
git switch -c exp/03-persistence-migration
git add src/ migrations/
git commit -m "feat: persist favorites and add versioned migration"
git push -u origin exp/03-persistence-migration
```

---

# 任务四：综合收口

## 任务目标

用一个请求贯穿三层，验证整条链路，并讲清各层职责。

## 需求

1. 完成 `GET /api/search` 的完整链路：Controller 解析查询，Service 校验关键词并去重，Repository 返回结果。
2. 空关键词或纯空白关键词返回空列表，不报错。
3. 写一个契约测试：搜索返回结构正确；收藏成功后能查回；重复收藏返回 409。
4. 在报告中说明一次请求依次穿过哪几层、每层各自做什么。

## 验收标准

| 验收项 | 具体要求 |
|--------|----------|
| 链路贯通 | 一个搜索请求经三层返回，结果结构符合契约 |
| 边界处理 | 空关键词返回空列表 |
| 契约测试 | 搜索与收藏的闭环测试通过 |
| 职责说明 | 能说清 Controller、Service、Repository 各自边界 |

## 提交要求

```bash
git switch -c exp/04-synthesis
git add src/ tests/
git commit -m "feat: wire search through the three layers with contract tests"
git push -u origin exp/04-synthesis
```

---

# 任务五：最小 JWT 登录与校验

## 任务目标

用 JWT 完成一次最小可用的登录与令牌校验，让受保护接口拒绝未授权请求。

## 需求

1. 实现 `POST /api/login`：校验用户名与口令，成功后返回 JWT（`token` 字段）。
2. 用一个可注入的依赖校验 `Authorization: Bearer <token>`：缺失或无效时返回 401。
3. 让收藏的写操作（`POST`、`DELETE`）在未带有效令牌时返回 401。
4. 口令可以简单哈希存放，密钥从环境变量读取。
5. 本任务只做最小可用，不涉及套餐授权、免费额度与注入防护专项。

## 验收标准

| 验收项 | 具体要求 |
|--------|----------|
| 登录可用 | 正确凭证换回令牌，错误凭证返回 401 |
| 校验生效 | 缺失或篡改令牌访问受保护接口返回 401 |
| 放行正确 | 携带有效令牌时写操作正常 |
| 密钥外置 | 密钥从环境变量读取，不写死在代码里 |

## 提交要求

```bash
git switch -c exp/05-auth
git add src/ tests/
git commit -m "feat: add minimal JWT login and token verification"
git push -u origin exp/05-auth
```

---

# 综合验收标准

| 验收项 | 具体要求 |
|--------|----------|
| 三层结构 | `api` / `service` / `repository` 目录清晰，两个协议抽象到位 |
| 接口契约 | 约定表中的端点齐全，状态码语义正确 |
| 持久化 | 收藏落 SQLite，主键约束生效 |
| 迁移 | 能演示一次表结构升级与回滚 |
| 综合链路 | 一个请求贯穿三层的契约测试通过 |
| 认证 | 最小 JWT 登录与校验可用，受保护接口正确返回 401 |
| 测试 | 测试全部通过，覆盖正常与错误路径 |
| 提交历史 | 五个任务分别有独立分支与提交，信息符合约定式规范 |

---

# 实验报告要求

将五个任务的提交记录汇总，提交一份实验报告，包含：

1. **项目概述**：服务实现了哪些功能，三层各自承担什么。
2. **接口清单**：端点、方法、状态码一览。
3. **迁移说明**：演示的那次表结构演进，升级与回滚分别怎么做。
4. **认证设计**：令牌如何签发与校验，密钥从哪里来。
5. **遇到的问题及解决过程**（至少 3 个）。
6. **实验收获与反思**。

---

# 评分参考

| 部分 | 分值 | 说明 |
|------|------|------|
| 任务一：三层骨架 | 20% | 目录清晰、协议抽象、依赖注入 |
| 任务二：REST 契约 | 20% | 端点齐全、状态码正确、契约模型合理 |
| 任务三：持久化与迁移 | 20% | 落库可用、迁移可升级可回滚 |
| 任务四：综合收口 | 20% | 链路贯通、契约测试通过、职责说明清晰 |
| 任务五：最小 JWT | 10% | 登录与校验可用，密钥外置 |
| 实验报告 | 10% | 内容完整、反思深入 |
