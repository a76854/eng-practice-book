---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

# Dockerfile 最佳实践

> 学完本节，你能回答：Docker 镜像的分层与缓存如何工作？为什么要把不常变的依赖清单放在频繁变动的业务代码之前？多阶段构建如何把编译时依赖与运行时镜像分离？

> 合理的顺序，本身就是效率。

## Dockerfile 的本质

每一行 Dockerfile 指令都会在上一层的基础上产生一个新的只读层（layer），最终镜像是这些层的叠加。运行时在此之上挂载一个可写层，容器内的修改只落在可写层，不污染镜像层。

- `FROM`：起始层，通常选 `python:3.12-slim` 这类裁剪过的基座，比 `python:3.12` 小数百 MB，且已包含最小的 `apt` 源。
- `RUN`：执行命令并固化结果为一层，如 `apt-get install` 或 `pip install`。
- `COPY`：把构建上下文中的文件拷入镜像，形成新层。
- `ENV` / `WORKDIR` / `EXPOSE` / `CMD`：元数据或运行时默认，不产生重量级层但影响可观测与启动。

> **类比叠加**：镜像像“千层蛋糕”，每一层都是上一层的增量；缓存命中时直接复用已烤好的层，失效时该层及之后所有层重烤。

## 层缓存

Docker 构建时会为每条指令计算缓存键：指令文本 + 被 `COPY` 的文件内容的哈希 + 前一层的哈希。若三者均未变，则直接命中缓存，跳过执行；若任一变化，则该层及之后所有层失效重建。

由此导出两条黄金规则：

1. **把最不常变的放最前**：依赖清单（`requirements.txt`、`pyproject.toml`）数周才变一次，应先 `COPY` 并 `RUN pip install`，让该层长期命中缓存；业务代码（`src/`）每天都变，应后 `COPY`，避免频繁使依赖层失效。
2. **合并可合并的 `RUN` 并清理缓存**：如 `apt-get update && apt-get install -y ... && rm -rf /var/lib/apt/lists/*` 写在同一 `RUN`，既减少层数，又避免 `apt` 缓存留在镜像中。

反例：若先 `COPY . .` 再 `RUN pip install -r requirements.txt`，则任何业务文件的改动都会使 `pip install` 层失效，CI 每次都要重装依赖，构建时间从秒级退化为分钟级。

## 多阶段构建

多阶段构建用多个 `FROM` 段落：前一阶段用重型基座完成编译、安装或前端打包，后一阶段仅 `COPY --from=builder` 产物到轻量运行时。优势是运行时镜像不含编译器、源码与中间缓存，体积与攻击面同步下降。

文档查询后端的典型二阶段：

- `builder` 阶段用 `python:3.12`，装好依赖并执行前端打包（若含前端）；
- `runtime` 阶段用 `python:3.12-slim`，仅拷入已安装的 `site-packages`、`src/` 与前端静态产物。

实验八的 `labs/lab08_fullstack_container/starter/Dockerfile` 为保持“最小可运行”未显式分段，但已体现多阶段的核心思想：只拷入需要的 `requirements.txt` 与 `src/`，避免把 `labs/`、`book/` 等无关上下文送入镜像；若需前端，可在同仓增加 `FROM node:20 AS frontend-builder` 再 `COPY --from=frontend-builder /app/dist`。

## 最小可用原则与安全细节

- **选择性 `COPY`**：只拷 `requirements.txt` 与 `src/`，不 `COPY . .`，既加速上下文传输，也避免把 `.git`、`.venv`、数据文件误入镜像。
- **`--no-cache-dir` 与 `--no-install-recommends`**：`pip install --no-cache-dir` 不保留 wheel 缓存，`apt-get install --no-install-recommends` 不装推荐但非必须的包，二者共同控制镜像体积。
- **非 root 运行（生产建议）**：教学样例为简洁未切用户，生产应在 `RUN useradd -m app && USER app` 后再 `CMD`，降低容器逃逸后的权限。
- **`EXPOSE` 仅声明**：`EXPOSE 8000` 不自动发布端口，发布由 `docker run -p` 或 Compose 的 `ports` 决定，声明的价值在于文档化与 `docker inspect` 可见。

> **环境约定**：本书面向 Linux，镜像内路径统一为 Linux 风格 `/app`、`/data`，构建上下文的路径分隔符由 Docker 客户端处理，正文中的 `COPY src/ ./src/` 在 Linux 环境均一致。

## 解析内联 Dockerfile 的层与缓存

示例：解析内联 Dockerfile 的层与缓存：

```{code-cell} ipython3
import re

# 内联 Dockerfile 示例（与实验八 starter 同构，无需依赖仓库中的真实文件）
DOCKERFILE = """\
FROM python:3.12-slim
WORKDIR /app

# 依赖层：清单数周才变，安装结果可长期命中缓存
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 代码层：业务代码每天在变，只让这一层失效
COPY src/ ./src/

ENV PYTHONPATH=/app/src
ENV PYTHONDONTWRITEBYTECODE=1
ENV DOCSEARCH_DATA_DIR=/data
RUN mkdir -p /data

EXPOSE 8000
CMD ["uvicorn", "docsearch.main:app", "--host", "0.0.0.0", "--port", "8000"]
"""
lines = DOCKERFILE.splitlines()

# 解析指令：忽略空行与注释，提取指令名与参数
directives: list[tuple[str, str, int]] = []  # (指令, 参数, 行号)
for idx, raw in enumerate(lines, 1):
    s = raw.strip()
    if not s or s.startswith("#"):
        continue
    m = re.match(r"^([A-Z]+)\s*(.*)$", s)
    if m:
        directives.append((m.group(1), m.group(2), idx))

print("=== Dockerfile 指令序列（层视角） ===")
for cmd, arg, lineno in directives:
    print(f"  L{lineno:02d} {cmd:10s} {arg[:72]}")

# 统计与断言：教学样例应含的关键层
cmds = [c for c, _, _ in directives]
for name in ("FROM", "COPY", "RUN", "EXPOSE", "CMD"):
    assert name in cmds, f"缺少 {name}"
print("\n层统计:", {k: cmds.count(k) for k in sorted(set(cmds))})

# 缓存友好的关键在顺序：清单的 COPY 在安装之前，代码的 COPY 在安装之后
dep_copy = next(ln for c, arg, ln in directives if c == "COPY" and "requirements.txt" in arg)
pip_ln = next(ln for c, arg, ln in directives if c == "RUN" and "pip install" in arg)
code_copy = next(ln for c, arg, ln in directives if c == "COPY" and "src/" in arg)
print("\n依赖清单 COPY 行:", dep_copy, "| pip install 行:", pip_ln, "| 业务代码 COPY 行:", code_copy)
assert dep_copy < pip_ln < code_copy
print("COPY 顺序 OK：清单在安装前，代码在安装后（代码改动不会使依赖层失效）")

# 体积与启动细节
assert "--no-cache-dir" in DOCKERFILE, "建议 pip install --no-cache-dir"
assert "PYTHONDONTWRITEBYTECODE" in DOCKERFILE, "建议关闭字节码写入，省去无谓的体积"
print("体积控制 OK：--no-cache-dir 与 PYTHONDONTWRITEBYTECODE 均已配置")

print("\n解析结论：依赖清单与业务代码分层，顺序满足缓存友好，且包含体积控制细节")
```

```bash
# 本地查看 Dockerfile 层
cat labs/lab08_fullstack_container/starter/Dockerfile
# 若已安装 Docker，可查看构建上下文与解析结果（本章不要求守护进程）
docker build -f labs/lab08_fullstack_container/starter/Dockerfile --dry-run 2>&1 | head -n 20
```

## 为何 COPY 顺序决定构建速度

示例：COPY 顺序与构建缓存：

```{code-cell} ipython3
import hashlib


# 模拟 Docker 的层缓存键：hash(指令文本 + 文件内容哈希 + 前一层哈希)
def layer_hash(instruction: str, file_content: str | None, prev_hash: str) -> str:
    h = hashlib.sha256()
    h.update(instruction.encode())
    if file_content is not None:
        h.update(hashlib.sha256(file_content.encode()).digest())
    h.update(prev_hash.encode())
    return h.hexdigest()[:12]


def simulate_build(copy_order: str) -> list[str]:
    """copy_order 为 good 时先拷清单再装依赖，为 bad 时一次性 COPY . ."""
    prev = "from:python3.12-slim"
    layers: list[str] = []
    # 依赖清单（数周才变）
    requirements = "fastapi==0.141.1\nuvicorn==0.34.0"
    # 业务代码（每天在变）
    app_v1 = "def search(q: str) -> list[str]:\n    return []"
    app_v2 = "def search(q: str) -> list[str]:\n    return [q]  # 业务改动"
    if copy_order == "good":
        h1 = layer_hash("COPY requirements.txt", requirements, prev)
        layers.append(f"COPY requirements.txt -> {h1}")
        h2 = layer_hash("RUN pip install", requirements, h1)
        layers.append(f"RUN pip install       -> {h2}")
        h3 = layer_hash("COPY src/", app_v1, h2)
        layers.append(f"COPY src/ v1          -> {h3}")
        h3b = layer_hash("COPY src/", app_v2, h2)
        layers.append(f"COPY src/ v2          -> {h3b} (仅此层失效)")
        layers.append(f"复用 pip 层: {h2} 命中缓存")
    else:
        h1 = layer_hash("COPY . .", requirements + app_v1, prev)
        layers.append(f"COPY . . v1           -> {h1}")
        h2 = layer_hash("RUN pip install", requirements + app_v1, h1)
        layers.append(f"RUN pip install v1    -> {h2}")
        h1b = layer_hash("COPY . .", requirements + app_v2, prev)
        layers.append(f"COPY . . v2           -> {h1b} (业务改动导致整层失效)")
        h2b = layer_hash("RUN pip install", requirements + app_v2, h1b)
        layers.append(f"RUN pip install v2    -> {h2b} (被迫重装依赖)")
    return layers


print("=== 好顺序：先清单后代码（缓存友好） ===")
for line in simulate_build("good"):
    print(" ", line)

print("\n=== 差顺序：一次性 COPY . . ===")
for line in simulate_build("bad"):
    print(" ", line)

good = simulate_build("good")
bad = simulate_build("bad")
assert "命中缓存" in good[-1]
assert bad[1] != bad[3]
print("\n缓存行为校验通过：好顺序只让代码层失效，差顺序连带依赖层一起重来")
```

> **工程启示**：Dockerfile 不是脚本的堆砌，而是对“变更频率”的显式排序。把最稳定的放最前、最易变的放最后，才能让缓存命中率最大化；多阶段则把“构建时工具”与“运行时依赖”解耦，二者共同决定镜像的构建速度与体积。与 [第1章 工程化项目结构](../../software_engineering/dev_meta_skills/engineering_project_structure.md) 的“可复现依赖”相互印证，Dockerfile 把依赖清单与目录布局的可复现性延伸到系统库与文件结构。

```bash
# 对比两种 COPY 顺序的构建时间思想实验（无需真实构建，纯文本推演）
# 好：COPY requirements.txt -> RUN pip install -> COPY src/  (代码改动仅重建最后一层)
# 差：COPY . .              -> RUN pip install -r requirements.txt (代码改动重建所有层)
```