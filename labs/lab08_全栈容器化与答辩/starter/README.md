# Lab08 starter 说明

本目录是实验八的起点骨架，对应 `book/part5_实验指导书/experiment08_里程碑BC_全栈容器化与答辩/index.md`，把全栈应用容器化并用 Compose 完成联调预演与答辩准备。

## 包含内容

- `Dockerfile`：后端最小镜像，基座 `python:3.12-slim`，选择性 COPY 与层缓存友好的顺序，`EXPOSE 8000` 与 `CMD ["python", "-m", "m2t.cli", "serve", "--host", "0.0.0.0", "--port", "8000"]`。
- `docker-compose.yml`：两服务编排，`backend` 带健康检查，`frontend` 为 `nginx:alpine`，通过 `depends_on` 的 `service_healthy` 表达启动依赖。
- 本 `README.md`：本地校验、部署步骤复述与答辩要点。

骨架保持“环境固化、拓扑声明、配置可预演”的交付分层，镜像只含 `m2t` 与运行时依赖，Compose 声明前后端在 `80` 与 `8000` 的协作，校验在无 Docker 时用 YAML 解析即足够。

## 本地校验（无需 Docker 守护进程）

```bash
# YAML 解析预演（Windows / macOS / Linux 一致）
python -c "import yaml; yaml.safe_load(open('docker-compose.yml', encoding='utf-8')); print('compose yaml ok')"
python -c "import pathlib; print('Dockerfile exists:', pathlib.Path('Dockerfile').exists())"

# 文本层面的 Dockerfile 检查
python -c "import pathlib; d=pathlib.Path('Dockerfile').read_text(); assert 'python:3.12-slim' in d; assert 'COPY m2t/' in d; print('Dockerfile ok')"

# 有 Docker 时的编排校验（可选）
docker compose -f docker-compose.yml config -q && echo "compose config ok"
```

## 部署步骤（复述到云或 VM）

本实验不要求真实云密钥与真实构建，验收以本地 YAML 预演与文档复述为准，映射如下：

1. 构建镜像：`docker build -f Dockerfile -t mtt-backend:lab08 .`，上下文仅含 `pyproject.toml` / `README.md` 与 `m2t/`，`labs/` 与 `book/` 不入镜像。
2. 编排启动：`docker compose up -d`，`backend` 先就绪，健康检查通过后 `frontend` 才被视为可用，日志可用 `docker compose logs -f` 观察。
3. 功能验收：`curl http://127.0.0.1:8000/api/health` 应回 `{"status": "ok"}`，浏览器打开 `http://127.0.0.1:80` 应见前端静态页，二者の `depends_on` 保证时序。
4. 持久化：`MTT_DATA_DIR=/data` 指向容器内 `/data`，云上可挂盘或对象存储，前后端的跨域由后端 CORS 放开，前端由 Nginx 托管静态。
5. 回滚思路：镜像以 tag 固化版本，发布时只改 Compose 的 `image` 或重建，上一 tag 可一键回退，做到可复现与可回滚。

> 跨域与端口：`EXPOSE 8000` 仅声明，发布由 Compose 的 `ports: ["8000:8000"]` 决定，`frontend` 的 `80:80` 对外，前后端在 Compose 网络内用服务名互联，对外则经宿主机端口。

## 答辩要点

答辩为 10 到 12 分钟陈述加提问，主线五节，每节 2 到 3 分钟：

1. 需求切片：里程碑 A 的 CLI 单机闭环如何演进为 B 的服务化与 C 的全栈可交付，8 个实验如何按顺序铺垫。
2. 架构选型：为何选 FastAPI 加 Vue3，前后端分层与 Pinia 状态边界，路由与存储的职责。
3. 外部集成与流式：ASR 多形状归一、LLM 脱敏与 SSE 增量渲染，首字时延与失败域。
4. 健壮性与质量门禁：ruff 加 mypy 加 pytest 的门禁，CI 如何拦截低质量合并，日志与降级。
5. 容器化与交付：Dockerfile 的层缓存与选择性 COPY，Compose 的健康检查与 `depends_on`，CI 的 `docker compose config -q` 预检。

提问准备：

- 为何先 `COPY pyproject.toml` 再 `COPY m2t/`，先拷全量会怎样导致缓存失效。
- `depends_on` 与健康检查的区别，`service_healthy` 如何避免前端在后端未就绪时就被访问。
- `EXPOSE` 与 `ports` 的分工，`restart: "no"` 在本地与云上的不同选型。
- 多阶段构建如何把编译时与运行时分离，本实验的单阶段教学版如何体现同一思想。

## 跨平台说明

- `python -c "import yaml; yaml.safe_load(...)"` 三平台一致，Windows 上路径用 `open('docker-compose.yml', encoding='utf-8')` 亦可。
- Dockerfile 与 Compose 的路径统一为 Linux 风格 `/app`、`/data`，在 Windows 宿主机上同样生成 Linux 镜像。
- `.dockerignore` 可按需忽略 `labs/`、`book/`、`.venv`、模型权重，保持构建上下文精简。

## 下一步

按实验文档步骤 3 至 6 完善镜像的 `pip install` 与 Compose 的环境变量，对照 `deploy-demo/Dockerfile.backend` 与反应 `deploy-demo/docker-compose.yml` 的最小两服务形态，准备演示与答辩。
