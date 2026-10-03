---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

# CI/CD 流水线

上一节让多个容器按依赖就绪地跑起来，可交付还差一步：怎么保证每一次改动都经过同样的检查，而不是靠人记得跑。第 2 章讲过“提交即校验”的 CI 概念与一份最小流水线，本节把它放进交付链条里。容器与编排就位之后，门禁要多守一道拓扑合法性，发布也要能从镜像回到具体的提交。本节先看人工上线的三处漏，再给出这条门禁链路的完整写法，最后补上发布与回滚。

## 从手动上线到自动化

手工上线常见三错：漏跑检查、环境漂移、回归测试。CI（持续集成）把“每次提交必经的校验”自动化，CD（持续交付/部署）把“已验证的产物可一键发布”自动化，二者共同构成“提交即验证、验证即门禁”的交付流水线。

- **CI**：在代码合入前自动完成风格检查、类型检查、单元测试与编排校验，失败则阻断合入。
- **CD**：在 CI 通过后自动完成构建、推送镜像、部署到预发或生产（本章聚焦 CI 与交付就绪，生产发布由运维策略决定是否自动）。

文档查询后端的门禁链路与此一一对应，四道关各守一端：

| 门禁 | 守什么 | 不过会怎样 |
| --- | --- | --- |
| `uv run ruff check src/` | 风格与常见缺陷 | 命中就红灯，合入被拦 |
| `uv run mypy src/` | 类型契约 | 同上 |
| `uv run pytest -q` | 行为回归 | 同上 |
| `docker compose config -q` | 拓扑合法性 | 同上 |

前三道守代码，第四道守配置。顺序也有讲究：从快到慢排，最便宜的检查先跑，失败早暴露，不浪费后面的时间。

## 仓库自带的执行器

GitHub Actions 可以理解成仓库自带的执行器：你在仓库里放一份 YAML，声明“什么时候跑、在哪台机器上跑、跑哪些命令”，GitHub 就会在满足条件时替你开一台临时机器，把命令跑一遍，并把结果与日志挂在这次提交或这次 PR 上。失败就是红灯，也可以把它设为合并的前置条件。

它要解决的问题很朴素：人总会忘。忘跑测试、忘更新依赖、只在本机验证过。把这些命令从“口头约定”搬进仓库里的 YAML，检查就跟着提交走，谁来提交都一样。

这份声明放在 `.github/workflows/` 目录下，需要交代清楚四件事：触发时机（推送或开 PR）、运行环境（用哪台临时机器）、执行步骤（按顺序跑哪些命令）、失败时的表现。本节的内联示例就是这四样的最小写法。

> **中立性说明**：GitHub Actions 适合 GitHub 托管项目的开箱即用；GitLab CI、Jenkins、CircleCI 等在自托管与企业集成上各有优势，门禁链路的思想一致：把“本地可跑”的校验固化为“提交必跑”的自动化。

## 工作流示例

```yaml
name: CI
on: { push: {}, pull_request: {} }
jobs:
  verify:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install uv
      - run: uv sync --dev
      - run: uv run ruff check src/
      - run: uv run mypy src/
      - run: uv run pytest -q
      - run: docker compose -f docker-compose.yml config -q
```

逐项解读：

- `on`：触发时机。`push` 保证每次推送都验证，`pull_request` 保证合入前在目标分支的上下文里再验证一次，两者叠加覆盖“分支推送”与“合入门禁”两类场景。
- `runs-on`：运行环境，这里是一台临时的 Ubuntu 机器，用完即弃，所以每一步都要能从零装出环境。
- `actions/checkout` 与 `actions/setup-python`：把代码检出到这台机器上，并固定 Python 版本，避免“本地 3.12 通过、CI 3.11 失败”。多版本矩阵的写法见 [CI/CD 与代码质量](../../software_engineering/code_quality/testing_coverage_and_ci.md)。
- `pip install uv` 与 `uv sync --dev`：装上 `uv` 并按 `pyproject.toml` 与 `uv.lock` 复现依赖，与上一节镜像里的安装方式同源，本地和 CI 装出的是同一套依赖。
- `uv run …`：在项目环境里依次执行风格、类型与行为三道关。
- `docker compose … config -q`：不启动容器，只校验 Compose YAML 合法性与可渲染性，守拓扑这道关。

> **环境约定**：本书面向 Linux，流水线默认在 `ubuntu-latest` 的 Linux 执行器上运行，本地开发均用 `.venv` 复现同一套命令，保证“本地绿、CI 亦绿”。

## 门禁的顺序与本地复现

四道门禁的耗时差着量级，顺序因此有讲究：最便宜的检查先跑，失败早暴露，后面的时间就省下来了。

| 顺序 | 门禁 | 大致耗时 | 守什么 |
| --- | --- | --- | --- |
| 1 | `uv run ruff check src/` | 秒级 | 风格与常见缺陷 |
| 2 | `uv run mypy src/` | 秒级到十几秒 | 类型契约 |
| 3 | `uv run pytest -q` | 十几秒到分钟级 | 行为回归 |
| 4 | `docker compose config -q` | 秒级 | 拓扑合法性 |

把这笔账算成数：假设风格检查 5 秒、类型检查 8 秒、测试 30 秒、编排校验 2 秒，合计 45 秒。若风格检查在第一道就失败，只付出 5 秒即可停下，比“全跑完再看结果”省下约九成时间。提交越频繁，这笔账越值得算。

比顺序更重要的是可复现：流水线里跑的每一条命令，开发者都应该能在本机跑一遍，红灯不必等推送才发现。

```bash
# 本地复刻流水线的四道门禁（都在 .venv 里有等价写法）
.venv/bin/python -m ruff check src/
.venv/bin/python -m mypy src/
.venv/bin/python -m pytest -q
.venv/bin/python -c "import yaml; yaml.safe_load(open('docker-compose.yml'))"

# 有 Docker 时，编排校验用同一份声明
docker compose -f docker-compose.yml config -q && echo "compose config ok"
```

## 发布与回滚

CI 通过之后，产物才算“可交付”，接下来的问题是把它发出去，以及出错时怎么退回来。

关键在一个约定：**发布的东西必须不可变**。镜像的两个常见标签风格，差别在回滚时最能体现：

| 标签风格 | 例子 | 回滚时的问题 |
| --- | --- | --- |
| 浮动标签 | `docsearch:latest` | 下次拉到的可能是更深的新版本，退不回指定那个 |
| 不可变标签 | `docsearch:8f3c21a`（提交号） | 与提交一一对应，指回上一个标签即可复原 |

用提交号打标签是最省事的做法：构建时取当前提交的短哈希作为标签，产物与代码一一对应，回滚就是把 Compose 里的 `image` 指回上一个标签再拉起，而不是登上服务器改文件。若要求更严格，可以按镜像摘要固定，因为标签可以被覆盖，摘要不会：

```bash
# 构建时用提交号做标签，产物与提交一一对应
docker build -f Dockerfile -t docsearch:$(git rev-parse --short HEAD) .
docker push docsearch:$(git rev-parse --short HEAD)

# 回滚 = 把配置指回上一个不可变标签，再按声明式拓扑重新拉起
docker compose pull
docker compose up -d
```

前几节把“构建输入”固化成 Dockerfile 与锁文件，这一步把“发布的是哪个产物”也固定下来。两件事合起来，才谈得上“回滚到任意历史版本可复现”：同一份提交、同一套锁文件、同一个镜像标签，构建出的运行环境就是同一个。

## 本节小结

- 人工上线常在三处出错：漏跑检查、环境漂移、回归靠记忆；CI 把提交必经的校验自动化，CD 把已验证产物的一键发布自动化。
- GitHub Actions 是仓库自带的执行器：放一份 YAML 交代触发时机、运行环境、执行步骤与失败表现，推送或开 PR 时自动跑。
- 交付门禁有四道：风格、类型、行为、拓扑；从快到慢排，最便宜的检查先跑，失败早暴露。
- 门禁与本地命令必须一致，本地 `.venv` 能复现 CI 的每一步，红灯才能在提交前发现。
- 发布用不可变标签或镜像摘要固定产物，回滚是把配置指回上一个标签再按拓扑拉起，而不是上服务器改文件。
