---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

# Docker Compose 编排

上一节把单个应用装进了镜像，可真实系统不止一个进程：前端静态资源要有人托管，后端要提供接口，将来的数据库还要能被后端连上。容器一个个起没问题，麻烦在于它们之间的关系：谁先起、谁等谁就绪、谁对外暴露端口。本节把这些关系从口头约定变成一份可校验的声明，用 Compose 描述文档查询应用的最小编排，并用 YAML 解析在没有 Docker 的机器上验证它。

## 从单容器到多容器

单个容器只解决“一个进程的可复现”，真实系统是多个进程的协作：前端静态资源需由 Nginx 托管、后端提供 `/api` 动态接口、持久化可能由数据库或文件卷承载。三者的关系是拓扑而非清单：谁依赖谁、谁先就绪、谁暴露哪一端口、谁共享哪一数据卷，都需要声明式地描述而非口头约定。

Docker Compose 用一个 `docker-compose.yml` 声明整个拓扑，常用的原语并不多：

| 原语 | 作用 | 本节示例 |
| --- | --- | --- |
| `services` | 声明每个容器如何构建与运行 | `backend` 与 `frontend` 两个服务 |
| `build` | 指定构建上下文与 Dockerfile | `{ context: ., dockerfile: Dockerfile }` |
| `image` | 直接使用现成镜像 | `nginx:alpine` |
| `ports` | 宿主机与容器的端口映射 | `8000:8000`、`80:80` |
| `environment` | 向容器注入环境变量 | `DOCSEARCH_DATA_DIR=/data` |
| `healthcheck` | 定义“怎样算就绪” | 探测 `/api/health` |
| `depends_on` | 声明服务之间的依赖 | `frontend` 依赖 `backend` |

`docker compose up` 按这份拓扑一键拉起，`docker compose config` 能在不启动守护进程的前提下校验 YAML 是否合法。

类比：若 Dockerfile 是“一道菜的配方”，Compose 就是“一桌宴席的上菜顺序与摆盘图”。

## 核心原语与运行时契约

以下面的内联拓扑为例（教学最小二服务，对应文档查询应用的“前端静态 + 后端动态”分离）：

```yaml
services:
  backend:
    build: { context: ., dockerfile: Dockerfile }
    environment: { DOCSEARCH_DATA_DIR: /data }
    healthcheck: { test: ["CMD", "python", "-c", "import urllib.request..."], interval: 30s }
    ports: ["8000:8000"]
  frontend:
    image: nginx:alpine
    ports: ["80:80"]
    depends_on: { backend: { condition: service_healthy } }
```

- `services.backend.build`：后端的镜像如何构建（上下文与 Dockerfile 路径），构建输入与上一节的层缓存直接相关。
- `services.backend.healthcheck`：后端何时算“就绪”。用 `urllib.request` 探测 `http://127.0.0.1:8000/api/health`，`interval` / `timeout` / `retries` / `start_period` 共同定义“多久探一次、探多久算超时、重试几次、启动后宽限多久”。
- `services.frontend.image`：前端用现成的 `nginx:alpine`，不需构建，拉取即可，体现“能用现成镜像就不自建”的最小可用原则。
- `ports`：`宿主机:容器` 的端口映射。`8000:8000` 让宿主机直连后端便于调试，`80:80` 让浏览器直连 Nginx。生产可改为仅暴露 80，由 Nginx 反向代理到后端内网端口。
- `restart: "no"`：教学演示选择不自动重启，便于观察失败；生产可按需改为 `unless-stopped`。

## 启动依赖与就绪依赖

`depends_on` 有新旧两种写法，差别不在语法而在语义，这是编排里最容易踩的一处：

| 写法 | 保证什么 | 不保证什么，风险在哪 |
| --- | --- | --- |
| `depends_on: [backend]` | 只保证容器创建顺序在后端之后 | 不保证后端已监听，前端转发即 502 |
| `depends_on: { backend: { condition: service_healthy } }` | 等后端健康检查通过才启动前端 | 需要后端提供健康探针，启动时机稍晚 |

两种写法都写在文件里，效果却差着一层：前者是“启动先后”，后者是“就绪先后”。健康检查把“后端算不算能用”从人工观察变成了机器可判定的条件，也就把等待这件事交给了编排工具。

## 拓扑的校验方式

配置文件的好处是可以脱离运行时校验。有 Docker 时，`docker compose config -q` 会把整份声明解析一遍，检查语法、变量替换与可渲染性，合法就零退出码；没有 Docker 时，用 YAML 解析确认服务、依赖、端口与环境变量是否写对，也能拦下绝大多数笔误。两种校验都在本机与 CI 里可跑，拓扑因此不必等真正拉起容器才验证。

```bash
# 有 Docker：完整校验声明合法性（-q 静默，合法即零退出）
docker compose -f labs/lab08_fullstack_container/starter/docker-compose.yml config -q && echo "compose config ok"

# 无 Docker：用 YAML 解析核对关键字段
.venv/bin/python - <<'PY'
import yaml
compose = yaml.safe_load(open('labs/lab08_fullstack_container/starter/docker-compose.yml', encoding='utf-8'))
services = compose['services']
assert 'backend' in services and 'frontend' in services
assert services['frontend']['depends_on']['backend']['condition'] == 'service_healthy'
assert 'api/health' in str(services['backend']['healthcheck']['test'])
print('services:', list(services), '| 就绪依赖 OK')
PY
```

## 健康检查与就绪判断

`depends_on` 的两种写法在故障注入下差别很大。把上表的结论按时序摆开：写法 A 里，前端容器在后端容器创建之后就启动，此时后端可能还在迁移数据库或预热缓存，前端一开始转发，用户就看到 502；写法 B 里，前端一直等到后端的 `/api/health` 能正常响应才开始启动，等于把“人工等一等”交给了编排工具执行。

依赖再往下加一层，这套声明也照样成立：

| 服务 | 依赖谁 | 启动顺序 |
| --- | --- | --- |
| `db` | 无 | 1 |
| `backend` | `db` 健康 | 2 |
| `frontend` | `backend` 健康 | 3 |

三段连成一条链，任何一环没就绪，后面的都不会被拉起。这套写法的成本也很直白：每个被依赖的服务都得提供一个能反映“我能不能干活”的探针，探针写得太宽松等于没写，写得太严格会让上游一直等。

## 本节小结

- 单个容器只解决一个进程的可复现，真实系统是多个进程的协作，关系要写成声明式拓扑。
- Compose 用 `services`、`build`、`image`、`ports`、`environment`、`healthcheck`、`depends_on` 这几样原语描述整个拓扑，`docker compose up` 一键拉起。
- `depends_on` 的普通写法只管启动顺序，`condition: service_healthy` 才管就绪顺序，能避免前端在后端还没监听时转发而报 502。
- `healthcheck` 把“怎样算就绪”从人工观察变成机器可判定的条件，探针路径与上一章的错误码与可观测约定相连。
- 拓扑可以脱离容器运行时用 YAML 解析来校验，本地和 CI 里都能跑，这是“配置可预演”的最小形态。
