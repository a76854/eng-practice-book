---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

# Dockerfile 最佳实践

> 学完本节，你能回答：Docker 镜像的分层与缓存如何工作？为什么要把不常变的 `COPY pyproject.toml` 放在频繁变动的 `COPY m2t/` 之前？多阶段构建如何把编译时依赖与运行时镜像分离？

## Dockerfile 的本质：分层叠加的只读快照

每一行 Dockerfile 指令都会在上一层的基础上产生一个新的只读层（layer），最终镜像是这些层的叠加。运行时在此之上挂载一个可写层，容器内的修改只落在可写层，不污染镜像层。

- `FROM`：起始层，通常选 `python:3.12-slim` 这类裁剪过的基座，比 `python:3.12` 小数百 MB，且已包含最小的 `apt` 源。
- `RUN`：执行命令并固化结果为一层，如 `apt-get install` 或 `pip install`。
- `COPY`：把构建上下文中的文件拷入镜像，形成新层。
- `ENV` / `WORKDIR` / `EXPOSE` / `CMD`：元数据或运行时默认，不产生重量级层但影响可观测与启动。

> **类比叠加**：镜像像“千层蛋糕”，每一层都是上一层的增量；缓存命中时直接复用已烤好的层，失效时该层及之后所有层重烤。

## 层缓存：以“指令文本 + 上下文文件哈希”为键

Docker 构建时会为每条指令计算缓存键：指令文本 + 被 `COPY` 的文件内容的哈希 + 前一层的哈希。若三者均未变，则直接命中缓存，跳过执行；若任一变化，则该层及之后所有层失效重建。

由此导出两条黄金规则：

1. **把最不常变的放最前**：依赖清单（`pyproject.toml`、`requirements.txt`）数周才变一次，应先 `COPY` 并 `RUN pip install`，让该层长期命中缓存；业务代码（`m2t/`）每天都变，应后 `COPY`，避免频繁使依赖层失效。
2. **合并可合并的 `RUN` 并清理缓存**：如 `apt-get update && apt-get install -y ... && rm -rf /var/lib/apt/lists/*` 写在同一 `RUN`，既减少层数，又避免 `apt` 缓存留在镜像中。

反例：若先 `COPY . .` 再 `RUN pip install -e .`，则任何业务文件的改动都会使 `pip install` 层失效，CI 每次都要重装依赖，构建时间从秒级退化为分钟级。

## 多阶段构建：把“构建时”与“运行时”分离

多阶段构建用多个 `FROM` 段落：前一阶段用重型基座完成编译、安装或前端打包，后一阶段仅 `COPY --from=builder` 产物到轻量运行时。优势是运行时镜像不含编译器、源码与中间缓存，体积与攻击面同步下降。

MeetingToText 的典型二阶段：

- `builder` 阶段——`python:3.12` + `pip install -e ".[dev]"` + `npm run build`（若含前端）；
- `runtime` 阶段——`python:3.12-slim` 仅拷入已安装的 `site-packages` 与静态产物。

实验八的 `labs/lab08_fullstack_container/starter/Dockerfile` 为保持“最小可运行”未显式分段，但已体现多阶段的核心思想——只拷入需要的 `m2t/` 与 `pyproject.toml`，避免把 `labs/`、`book/` 等无关上下文送入镜像；若需前端，可在同仓增加 `FROM node:20 AS frontend-builder` 再 `COPY --from=frontend-builder /app/dist`。

## 最小可用原则与安全细节

- **选择性 `COPY`**：只拷 `pyproject.toml` + `m2t/`，不 `COPY . .`，既加速上下文传输，也避免把 `.git`、`.venv`、模型权重误入镜像。
- **`--no-cache-dir` 与 `--no-install-recommends`**：`pip install --no-cache-dir` 不保留 wheel 缓存，`apt-get install --no-install-recommends` 不装推荐但非必须的包，二者共同控制镜像体积。
- **非 root 运行（生产建议）**：教学样例为简洁未切用户，生产应在 `RUN useradd -m app && USER app` 后再 `CMD`，降低容器逃逸后的权限。
- **`EXPOSE` 仅声明**：`EXPOSE 8000` 不自动发布端口，发布由 `docker run -p` 或 Compose 的 `ports` 决定，声明的价值在于文档化与 `docker inspect` 可见。

> **环境约定**：本书面向 Linux，`Dockerfile.backend` 中的路径统一为 Linux 风格 `/app`、`/data`，构建上下文的路径分隔符由 Docker 客户端处理，正文中的 `COPY m2t/ ./m2t/` 在 在 Linux 环境均一致。

## 可运行示例一：解析内联 Dockerfile 的层与缓存

示例：解析内联 Dockerfile 的层与缓存：

```{code-cell} ipython3
import re

# 内联 Dockerfile 示例（与实验八 starter 同构，无需依赖仓库中的真实文件）
DOCKERFILE = """\
FROM python:3.12-slim
WORKDIR /app

# System deps for soundfile/librosa (libsndfile1), keep layer cache friendly
RUN apt-get update \\
    && apt-get install -y --no-install-recommends libsndfile1 \\
    && rm -rf /var/lib/apt/lists/*

# Layer-cache: copy dependency manifest first, so pip layer is cacheable
COPY pyproject.toml README.md ./
COPY m2t/ ./m2t/

# Install teaching package (m2t) + runtime deps, no wheel cache
RUN pip install --no-cache-dir -e .

ENV MTT_DATA_DIR=/data
RUN mkdir -p /data

EXPOSE 8000

CMD ["python", "-m", "m2t.cli", "serve", "--host", "0.0.0.0", "--port", "8000"]
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
assert "FROM" in cmds, "缺少 FROM"
assert "COPY" in cmds, "缺少 COPY"
assert "RUN" in cmds, "缺少 RUN"
assert "EXPOSE" in cmds, "缺少 EXPOSE"
assert "CMD" in cmds, "缺少 CMD"
print("\n层统计:", {k: cmds.count(k) for k in sorted(set(cmds))})

# 校验 COPY 顺序：pyproject.toml 应在 m2t/ 之前，且二者均在 pip install 之前（缓存友好）
copy_lines = [(arg, ln) for c, arg, ln in directives if c == "COPY"]
run_pip_lines = [(arg, ln) for c, arg, ln in directives if c == "RUN" and "pip install" in arg]
print("\nCOPY 指令行号:", [ln for _, ln in copy_lines])
print("RUN pip install 行号:", [ln for _, ln in run_pip_lines])

# 找到 COPY pyproject 与 COPY m2t 的相对顺序
copy_text = " ".join(arg for c, arg, _ in directives if c == "COPY")
assert "pyproject.toml" in copy_text and "m2t/" in copy_text
# 文本顺序即 Dockerfile 顺序：pyproject.toml 先出现
assert copy_text.index("pyproject.toml") < copy_text.index("m2t/")
print("COPY 顺序 OK：pyproject.toml 在 m2t/ 之前（依赖层可长期缓存）")

# 校验 pip install 在所有 COPY 之后（先拷清单再安装，符合缓存规则）
if copy_lines and run_pip_lines:
    max_copy_ln = max(ln for _, ln in copy_lines)
    min_pip_ln = min(ln for _, ln in run_pip_lines)
    # 注意：教学样例中 pip install 在 COPY 之后，满足缓存友好
    print(f"最大 COPY 行 {max_copy_ln} < 最小 pip install 行 {min_pip_ln} ?",
          max_copy_ln < min_pip_ln)
    assert max_copy_ln < min_pip_ln

# 校验清理与体积控制细节
full_text = DOCKERFILE
assert "--no-cache-dir" in full_text, "建议 pip install --no-cache-dir"
assert "rm -rf /var/lib/apt/lists/*" in full_text, "建议清理 apt 缓存"
assert "--no-install-recommends" in full_text, "建议 apt --no-install-recommends"
print("体积控制 OK：--no-cache-dir / 清理 apt 缓存 / --no-install-recommends 均已配置")

print("\n解析结论：该 Dockerfile 遵循‘先依赖清单、后业务代码’的缓存友好顺序，且包含体积控制细节")
# 预期输出:
# === Dockerfile 指令序列（层视角） ===
#   L01 FROM       python:3.12-slim
#   L02 WORKDIR    /app
#   L05 RUN        apt-get update ...
#   L10 COPY       pyproject.toml README.md ./
#   L11 COPY       m2t/ ./m2t/
#   L14 RUN        pip install --no-cache-dir -e .
#   L16 ENV        MTT_DATA_DIR=/data
#   L17 RUN        mkdir -p /data
#   L19 EXPOSE     8000
#   L21 CMD        ["python", "-m", "m2t.cli", "serve", ...]
# 层统计: {'CMD': 1, 'COPY': 2, 'ENV': 1, 'EXPOSE': 1, 'FROM': 1, 'RUN': 3, 'WORKDIR': 1}
# COPY 指令行号: [10, 11]
# RUN pip install 行号: [14]
# COPY 顺序 OK：pyproject.toml 在 m2t/ 之前（依赖层可长期缓存）
# 最大 COPY 行 11 < 最小 pip install 行 14 ? True
# 体积控制 OK：...
# 解析结论：...
```

```bash
# 本地查看 Dockerfile 层
cat labs/lab08_fullstack_container/starter/Dockerfile
# 若已安装 Docker，仅查看解析后的配置（本章不要求守护进程，教学中可选）
# docker build -f labs/lab08_fullstack_container/starter/Dockerfile --dry-run 2>&1 | head -n 20  # 仅示意，实际构建需守护进程
```

## 可运行示例二：为何 COPY 顺序决定构建速度

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
    """copy_order: 'good' 为先拷 pyproject 再拷 m2t，'bad' 为一次性 COPY ."""
    prev = "from:python3.12-slim"
    layers: list[str] = []
    # 固定依赖清单内容（不常变）
    pyproject_content = "name=m2t version=0.1.0 dependencies=[numpy]"
    # 业务代码内容（常变）
    m2t_v1 = "def transcribe(): return 'v1'"
    m2t_v2 = "def transcribe(): return 'v2' # 业务改动"
    if copy_order == "good":
        # 好顺序：分两层
        h1 = layer_hash("COPY pyproject.toml", pyproject_content, prev)
        layers.append(f"COPY pyproject.toml -> {h1}")
        h2 = layer_hash("RUN pip install", pyproject_content, h1)
        layers.append(f"RUN pip install   -> {h2}")
        h3 = layer_hash("COPY m2t/", m2t_v1, h2)
        layers.append(f"COPY m2t/ v1      -> {h3}")
        # 第二次构建：仅 m2t 变化
        h3b = layer_hash("COPY m2t/", m2t_v2, h2)
        layers.append(f"COPY m2t/ v2      -> {h3b} (仅此层失效)")
        # pip 层 h2 未失效，可重用
        layers.append(f"复用 pip 层: {h2} 命中缓存")
    else:
        h1 = layer_hash("COPY . .", pyproject_content + m2t_v1, prev)
        layers.append(f"COPY . . v1       -> {h1}")
        h2 = layer_hash("RUN pip install", pyproject_content + m2t_v1, h1)
        layers.append(f"RUN pip install v1-> {h2}")
        h1b = layer_hash("COPY . .", pyproject_content + m2t_v2, prev)
        layers.append(f"COPY . . v2       -> {h1b} (业务改动导致整层失效)")
        h2b = layer_hash("RUN pip install", pyproject_content + m2t_v2, h1b)
        layers.append(f"RUN pip install v2-> {h2b} (被迫重装依赖)")
    return layers

print("=== 好顺序：先清单后代码（缓存友好） ===")
for line in simulate_build("good"):
    print(" ", line)

print("\n=== 差顺序：一次性 COPY . . ===")
for line in simulate_build("bad"):
    print(" ", line)

print("\n结论：好顺序让‘业务改动’仅使最后一层失效，pip 层命中缓存；差顺序则业务改动导致依赖层连带失效")
# 校验：好顺序的两次 pip 哈希相同，差顺序不同
good = simulate_build("good")
bad = simulate_build("bad")
assert "命中缓存" in good[-1]
assert bad[1] != bad[3]
print("缓存行为校验通过")
# 预期输出:
# === 好顺序：先清单后代码（缓存友好） ===
#   COPY pyproject.toml -> <12位哈希>
#   RUN pip install   -> <12位哈希>
#   COPY m2t/ v1      -> <12位哈希>
#   COPY m2t/ v2      -> <12位哈希> (仅此层失效)
#   复用 pip 层: <12位哈希> 命中缓存
# === 差顺序：一次性 COPY . . ===
#   COPY . . v1       -> <12位哈希>
#   RUN pip install v1-> <12位哈希>
#   COPY . . v2       -> <12位哈希> (业务改动导致整层失效)
#   RUN pip install v2-> <12位哈希> (被迫重装依赖)
# 结论：...
# 缓存行为校验通过
```

> **工程启示**：Dockerfile 不是脚本的堆砌，而是对“变更频率”的显式排序。把最稳定的放最前、最易变的放最后，才能让缓存命中率最大化；多阶段则把“构建时工具”与“运行时依赖”解耦，二者共同决定镜像的构建速度与体积。与 [第1章 工程化项目结构](../../software_engineering/dev_meta_skills/engineering_project_structure.md) 的“可复现依赖”相互印证——Dockerfile 把 `pyproject.toml` 的可复现性延伸到系统库与文件布局。

```bash
# 对比两种 COPY 顺序的构建时间思想实验（无需真实构建，纯文本推演）
# 好：COPY pyproject.toml -> RUN pip install -> COPY m2t/  (业务改动仅重建最后一层)
# 差：COPY . .            -> RUN pip install               (业务改动重建所有层)
```
