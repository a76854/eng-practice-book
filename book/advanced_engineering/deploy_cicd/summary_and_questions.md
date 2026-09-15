---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

## 本章小结

- **部署演进以隔离边界为尺度**：物理机独占但笨重，虚拟机用 Hypervisor 换强隔离，容器用命名空间、控制组与联合文件系统换轻量可复现；Python 虚拟环境仅隔离 `site-packages`，容器则把系统库、文件布局、环境变量与端口一并固化，二者叠加才得到“在任何机器上可复现”的交付物。
- **Dockerfile 的艺术是排序与分层**：`FROM` 定基座、`COPY` 顺序定缓存命中率、`RUN` 合并与清理定镜像体积；把不常变的 `requirements.txt` 置于常变的 `src/` 之前并配合 `--no-cache-dir`，让业务改动仅使最后一层失效；多阶段则把构建时工具与运行时镜像解耦，体积与攻击面同步下降。
- **Compose 把多容器拓扑声明化**：`services` 声明如何构建与运行，`healthcheck` 定义何时就绪，`depends_on: {condition: service_healthy}` 把“启动先后”升级为“就绪先后”；内联示例的 Nginx(:80) 与后端(:8000) 二服务已足以演示“静态+动态”的最小联动，扩展 DB 时仅需在拓扑中增加健康依赖边。
- **流水线的价值是固化门禁而非多跑命令**：GitHub Actions 以工作流、作业、步骤三层组织“检出→装环境→装依赖→四道门禁”，`ruff` / `mypy` / `pytest` / `docker compose config -q` 分别守风格、类型、行为与拓扑；`push` + `pull_request` 双事件触发覆盖推送与合入窗口，失败早暴露且本地可等价复现，迟早在回归中收回成本。
- **贯穿启示**：本章把文档查询应用的“可运行”升级为“可交付”，用容器固化环境、用编排声明拓扑、用流水线固化门禁；与上一章的安全与健壮性底线共同构成上线的双重前提，先守住输入与故障的底线，再让每一次提交都自动经过可复现的构建与联调预检，全书理论篇至此收束。

## 思考题

1. **隔离的代价**：容器复用宿主机内核带来轻量，但也让“内核漏洞影响所有容器”与“强隔离需虚拟机”的权衡显现。在多租户场景中，你会如何论证“容器+虚拟机”混合方案的合理性？
2. **缓存的脆弱性**：`COPY . .` 为何会让依赖层的缓存频繁失效？若项目中既有 `requirements.txt` 又有锁文件，二者的 `COPY` 顺序与缓存键有何差异？
3. **多阶段的取舍**：多阶段构建减小了运行时镜像，但也让构建脚本更复杂。何时值得引入多阶段，何时保持单阶段更利于团队维护？
4. **健康检查的设计**：内联示例用 `urllib.request` 探测 `api/health` 作为健康标准，该端点应由谁实现、返回何种语义？若健康检查过于宽松或过于严格，会分别带来什么风险？
5. **就绪与启动的辨析**：`depends_on` 的普通形式与 `service_healthy` 形式在故障注入下有何不同表现？若后端健康检查在启动后 30 秒才通过，前端的重试策略应如何配合以避免 502？
6. **编排的边界**：Compose 适合单机声明式编排，Kubernetes 则面向多机与弹性伸缩。以文档查询的“搜索→收藏→摘要”链路为例，何种规模下需要从 Compose 迁移到 Kubernetes？
7. **门禁的分层与成本**：`ruff` / `mypy` / `pytest` 的执行成本差异显著，先快后慢的排序如何节省 CI 时间？若某次提交仅改动文档，是否应让所有门禁全量执行？
8. **本地与远端的对齐**：流水线固定 `python 3.12` 与依赖安装步骤，本地 `.venv` 如何保证与 CI 执行器一致？若 CI 用 `uv` 加速安装，本地是否也需同步以避免“本地绿、CI 红”？
9. **交付的可回滚性**：镜像的不可变标签（如 `docsearch:2026-08-27-abc123`）与浮动标签（如 `docsearch:latest`）在回滚时有何差异？Compose 如何通过固定镜像摘要而非标签来保证“回滚到任意历史版本可复现”？
10. **端到端预演**：仅用 `yaml` 解析与 `pathlib` 文本检查，能否在不启动 Docker 的前提下完成“Dockerfile 层序合法、Compose 拓扑就绪、CI 门禁齐全”的交付预演？这种预演的边界与局限是什么？

示例（本章贯通校验：用文本解析串联“演进思想 → Dockerfile → Compose → CI”最小闭环）：

```{code-cell} ipython3
import hashlib
import pathlib
import sqlite3
import sysconfig
import tempfile

import yaml

# 内联教学样例（与本章正文一致，无需依赖仓库中的真实文件）
DOCKERFILE = """\
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY src/ ./src/
ENV PYTHONPATH=/app/src
EXPOSE 8000
CMD ["uvicorn", "docsearch.main:app", "--host", "0.0.0.0", "--port", "8000"]
"""
COMPOSE_YAML = """\
services:
  backend:
    build: { context: ., dockerfile: Dockerfile }
    environment: { DOCSEARCH_DATA_DIR: /data }
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
      - run: pip install -r requirements.txt -r requirements-dev.txt
      - run: ruff check .
      - run: mypy src --ignore-missing-imports
      - run: python -m pytest -q
      - run: docker compose -f docker-compose.yml config -q
"""

print("=== 第 12 章贯通校验 ===")

# 1) 隔离与可复现：虚拟环境只隔离 site-packages，Dockerfile 把环境整体固化
print("\n[1] 隔离与可复现")
print("  purelib:", sysconfig.get_paths()["purelib"])
assert "site-packages" in sysconfig.get_paths()["purelib"]
assert "FROM python:3.12-slim" in DOCKERFILE
assert "requirements.txt" in DOCKERFILE
print("  Dockerfile 固化 OK：含 base image 与依赖清单")
print("  Dockerfile sha256:", hashlib.sha256(DOCKERFILE.encode()).hexdigest()[:16])

# 2) Dockerfile 层序：清单的 COPY 在安装之前，代码的 COPY 在安装之后
print("\n[2] Dockerfile 层序")
lines = [line.strip() for line in DOCKERFILE.splitlines() if line.strip() and not line.strip().startswith("#")]
dep_idx = next(i for i, line in enumerate(lines) if line.startswith("COPY") and "requirements.txt" in line)
pip_idx = next(i for i, line in enumerate(lines) if "pip install" in line)
code_idx = next(i for i, line in enumerate(lines) if line.startswith("COPY") and "src/" in line)
print(f"  清单 COPY 行索引: {dep_idx}, pip install 行索引: {pip_idx}, 代码 COPY 行索引: {code_idx}")
assert dep_idx < pip_idx < code_idx
print("  层序 OK：清单先于安装，代码后于安装，业务改动不会使依赖层失效")

# 3) Compose 拓扑：以就绪而非启动为依赖条件
print("\n[3] Compose 拓扑")
services = yaml.safe_load(COMPOSE_YAML)["services"]
assert "backend" in services and "frontend" in services
assert services["frontend"]["depends_on"]["backend"]["condition"] == "service_healthy"
assert "api/health" in str(services["backend"]["healthcheck"]["test"])
print("  services:", list(services.keys()))
print("  拓扑 OK：frontend --service_healthy--> backend")

# 4) CI 门禁：风格、类型、行为、拓扑四道齐全
print("\n[4] CI 流水线")
ci = yaml.safe_load(CI_YAML)
on_ci = ci.get("on", ci.get(True, {}))
assert isinstance(on_ci, dict) and "push" in on_ci and "pull_request" in on_ci
runs = [step.get("run", "") for step in ci["jobs"]["verify"]["steps"]]
for gate in ("ruff check", "mypy", "pytest", "docker compose"):
    assert any(gate in r for r in runs), f"缺少门禁 {gate}"
print("  on:", list(on_ci.keys()))
print("  流水线 OK：双事件触发，四道门禁串行")

# 5) 业务逻辑与部署形态解耦：同一套 sqlite3 代码在本地与镜像内行为一致
print("\n[5] 业务逻辑预演（部署形态不影响业务逻辑）")
with tempfile.TemporaryDirectory() as td:
    conn = sqlite3.connect(pathlib.Path(td) / "docsearch.db")
    conn.execute("CREATE TABLE favorites (doc_id TEXT PRIMARY KEY, added_at TEXT)")
    conn.execute("INSERT OR IGNORE INTO favorites VALUES (?, ?)", ("d1", "2026-08-27T10:00:00Z"))
    doc_id, added_at = conn.execute("SELECT doc_id, added_at FROM favorites").fetchone()
    print(f"  favorites: {doc_id} | {added_at}")
    assert doc_id == "d1"
    print("  存储 OK：收藏表逻辑与镜像形态无关")
    conn.close()

print("\n贯通结论：隔离思想 → Dockerfile 层缓存 → Compose 就绪依赖 → CI 门禁 → 业务逻辑，五段在本地文本预演中闭环")
```