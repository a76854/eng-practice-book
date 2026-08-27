---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

## 本章小结

- **部署演进以隔离边界为尺度**：物理机独占但笨重，虚拟机用 Hypervisor 换强隔离，容器用命名空间、控制组与联合文件系统换轻量可复现；Python 虚拟环境仅隔离 `site-packages`，容器则把系统库、文件布局、环境变量与端口一并固化，二者叠加才得到“在任何机器上可复现”的交付物。
- **Dockerfile 的艺术是排序与分层**：`FROM` 定基座、`COPY` 顺序定缓存命中率、`RUN` 合并与清理定镜像体积；把不常变的 `pyproject.toml` 置于常变的 `m2t/` 之前并配合 `--no-cache-dir` / `rm -rf /var/lib/apt/lists/*`，让业务改动仅使最后一层失效；多阶段则把构建时工具与运行时镜像解耦，体积与攻击面同步下降。
- **Compose 把多容器拓扑声明化**：`services` 声明如何构建与运行，`healthcheck` 定义何时就绪，`depends_on: {condition: service_healthy}` 把“启动先后”升级为“就绪先后”；内联示例的 Nginx(:80) 与后端(:8000) 二服务已足以演示“静态+动态”的最小联动，扩展 DB 时仅需在拓扑中增加健康依赖边。
- **流水线的价值是固化门禁而非多跑命令**：GitHub Actions 以工作流、作业、步骤三层组织“检出→装环境→装依赖→四道门禁”，`ruff` / `mypy` / `pytest` / `docker compose config -q` 分别守风格、类型、行为与拓扑；`push` + `pull_request` 双事件触发覆盖推送与合入窗口，失败早暴露且本地可等价复现，迟早在回归中收回成本。
- **贯穿启示**：本章把 MeetingToText 的“可运行”升级为“可交付”——用容器固化环境、用编排声明拓扑、用流水线固化门禁；与第 10 章的安全与健壮性底线共同构成上线的双重前提：先守住输入与故障的底线，再让每一次提交都自动经过可复现的构建与联调预检，全书理论篇至此收束。

## 思考题

1. **隔离的代价**：容器复用宿主机内核带来轻量，但也让“内核漏洞影响所有容器”与“强隔离需虚拟机”的权衡显现。在多租户场景中，你会如何论证“容器+虚拟机”混合方案的合理性？
2. **缓存的脆弱性**：`COPY . .` 为何会让依赖层的缓存频繁失效？若项目中既有 `pyproject.toml` 又有 `uv.lock`，二者的 `COPY` 顺序与缓存键有何差异？
3. **多阶段的取舍**：多阶段构建减小了运行时镜像，但也让构建脚本更复杂。何时值得引入多阶段，何时保持单阶段更利于团队维护？
4. **健康检查的设计**：内联示例用 `urllib.request` 探测 `api/health` 作为健康标准，该端点应由谁实现、返回何种语义？若健康检查过于宽松或过于严格，会分别带来什么风险？
5. **就绪与启动的辨析**：`depends_on` 的普通形式与 `service_healthy` 形式在故障注入下有何不同表现？若后端健康检查在启动后 30 秒才通过，前端的重试策略应如何配合以避免 502？
6. **编排的边界**：Compose 适合单机声明式编排，Kubernetes 则面向多机与弹性伸缩。以 MeetingToText 的“上传→转写→摘要”链路为例，何种规模下需要从 Compose 迁移到 Kubernetes？
7. **门禁的分层与成本**：`ruff` / `mypy` / `pytest` 的执行成本差异显著，先快后慢的排序如何节省 CI 时间？若某次提交仅改动文档，是否应让所有门禁全量执行？
8. **本地与远端的对齐**：流水线固定 `python 3.12` 与 `pip install -e ".[dev]"`，本地 `.venv` 如何保证与 CI 执行器一致？若 CI 用 `uv` 加速安装，本地是否也需同步以避免“本地绿、CI 红”？
9. **交付的可回滚性**：镜像的不可变标签（如 `m2t:2024-08-27-abc123`）与浮动标签（如 `m2t:latest`）在回滚时有何差异？Compose 如何通过固定镜像摘要而非标签来保证“回滚到任意历史版本可复现”？
10. **端到端预演**：仅用 `yaml` 解析与 `pathlib` 文本检查，能否在不启动 Docker 的前提下完成“Dockerfile 层序合法、Compose 拓扑就绪、CI 门禁齐全”的交付预演？这种预演的边界与局限是什么？

文件 `book/part4_advanced_engineering/chapter11_deploy_cicd/demo_summary.py`（本章贯通校验：用文本解析串联“演进思想 → Dockerfile → Compose → CI”最小闭环）：

```{code-cell} ipython3
# 文件 book/part4_advanced_engineering/chapter11_deploy_cicd/demo_summary.py
import pathlib, yaml, sys, hashlib, tempfile

from m2t.store import TaskStore

# 内联教学样例（与 11.1–11.4 正文一致，无需依赖仓库中的真实文件）
DOCKERFILE = """\
FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends libsndfile1 && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY pyproject.toml ./
COPY m2t/ ./m2t/
RUN pip install --no-cache-dir -e ".[dev]"
EXPOSE 8000
CMD ["python", "-m", "m2t.cli", "serve", "--host", "0.0.0.0", "--port", "8000"]
"""
COMPOSE_YAML = """\
services:
  backend:
    build: { context: ., dockerfile: Dockerfile }
    environment: { MTT_DATA_DIR: /data }
    healthcheck: { test: ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/api/health')"], interval: 30s }
    ports: ["8000:8000"]
  frontend:
    image: nginx:alpine
    ports: ["80:80"]
    depends_on: { backend: { condition: service_healthy } }
"""
CI_YAML = """\
name: CI
on: { push: {}, pull_request: {} }
jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
      - run: pip install -e ".[dev]" && pip install pyyaml
      - run: ruff check .
      - run: mypy m2t --ignore-missing-imports
      - run: python -m pytest -q
      - run: docker compose -f docker-compose.yml config -q
"""

print("=== Chapter 11 贯通校验 ===")

# 1) 部署演进思想：校验虚拟环境隔离 + Dockerfile 可复现性（11.1 + 11.2）
print("\n[1] 隔离与可复现")
import sysconfig
print("  purelib:", sysconfig.get_paths()["purelib"])
assert "site-packages" in sysconfig.get_paths()["purelib"]
content = DOCKERFILE
assert "FROM python:3.12-slim" in content
assert "libsndfile1" in content
print("  Dockerfile 固化 OK：含 base image + 系统库")
print("  Dockerfile sha256:", hashlib.sha256(content.encode()).hexdigest()[:16])

# 2) Dockerfile 层序校验（11.2）
print("\n[2] Dockerfile 层序")
lines = [l.strip() for l in content.splitlines() if l.strip() and not l.strip().startswith("#")]
copy_idx = [i for i, l in enumerate(lines) if l.startswith("COPY")]
pip_idx = [i for i, l in enumerate(lines) if "pip install" in l]
print(f"  COPY 行索引: {copy_idx}, pip install 行索引: {pip_idx}")
assert copy_idx and pip_idx and max(copy_idx) < min(pip_idx)
print("  层序 OK：COPY 清单在 pip install 之前（缓存友好）")

# 3) Compose 拓扑校验（11.3）
print("\n[3] Compose 拓扑")
compose = yaml.safe_load(COMPOSE_YAML)
services = compose["services"]
assert "backend" in services and "frontend" in services
assert services["frontend"]["depends_on"]["backend"]["condition"] == "service_healthy"
assert "api/health" in str(services["backend"]["healthcheck"]["test"])
print("  services:", list(services.keys()))
print("  depends_on:", services["frontend"]["depends_on"])
print("  拓扑 OK：frontend --service_healthy--> backend")

# 4) CI 流水线校验（11.4）
print("\n[4] CI 流水线")
ci = yaml.safe_load(CI_YAML)
on_ci = ci.get("on", ci.get(True, {}))
assert isinstance(on_ci, dict) and "push" in on_ci and "pull_request" in on_ci
steps = ci["jobs"]["verify"]["steps"]
runs = [s.get("run", "") for s in steps]
assert any("ruff check" in r for r in runs)
assert any("mypy" in r for r in runs)
assert any("pytest" in r for r in runs)
assert any("docker compose" in r for r in runs)
print("  on:", list(on_ci.keys()))
print("  steps:", len(steps), "步 | 门禁: ruff/mypy/pytest/compose 齐全")
print("  流水线 OK：push+pull_request 双触发，四道门禁串行")

# 5) 与教学包联动：TaskStore 仍可在容器化预演中工作（业务逻辑不受部署形态影响）
print("\n[5] 教学包联动（部署形态不影响业务逻辑）")
with tempfile.TemporaryDirectory() as td:
    db = pathlib.Path(td) / "ch11_summary.db"
    store = TaskStore(db)
    store.create("ch11-demo", "meeting.wav", full_text="容器化交付预演")
    row = store.get("ch11-demo")
    print(f"  TaskStore: {row['id']} | {row['filename']} | {row['status']}")
    assert row["id"] == "ch11-demo"
    print("  存储 OK：TaskStore 在本地预演中仍可工作")

print("\n贯通结论：隔离思想 → Dockerfile 层缓存 → Compose 就绪依赖 → CI 门禁 → 业务逻辑，五段在本地文本预演中闭环")
# 预期输出:
# === Chapter 11 贯通校验 ===
# [1] 隔离与可复现
#   purelib: .../site-packages
#   Dockerfile 固化 OK：含 base image + 系统库
#   Dockerfile sha256: <16位十六进制>
# [2] Dockerfile 层序
#   COPY 行索引: [...] , pip install 行索引: [...]
#   层序 OK：COPY 清单在 pip install 之前（缓存友好）
# [3] Compose 拓扑
#   services: ['backend', 'frontend']
#   depends_on: {'backend': {'condition': 'service_healthy'}}
#   拓扑 OK：frontend --service_healthy--> backend
# [4] CI 流水线
#   on: ['push', 'pull_request']
#   steps: 7 步 | 门禁: ruff/mypy/pytest/compose 齐全
#   流水线 OK：push+pull_request 双触发，四道门禁串行
# [5] 教学包联动（部署形态不影响业务逻辑）
#   TaskStore: ch11-demo | meeting.wav | pending
#   存储 OK：TaskStore 在本地预演中仍可工作
# 贯通结论：隔离思想 → Dockerfile 层缓存 → Compose 就绪依赖 → CI 门禁 → 业务逻辑，五段在本地文本预演中闭环
```
