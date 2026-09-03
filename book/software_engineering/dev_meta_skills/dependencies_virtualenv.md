---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

# 依赖与虚拟环境

学完本节，你能回答：

- 为什么每个 Python 项目都需要独立的虚拟环境？
- 虚拟环境、包管理器、项目管理工具三者之间是什么关系？
- 从 `pyproject.toml` 到可运行环境，完整的工作流是怎样的？

> 如果把 Python 比作一锅底汤，依赖就是调味料。有人要加辣，有人不要葱，有人过敏不能放花生——但全局环境只有一个碗，所有人的调料都往里面倒，最后谁也吃不好。虚拟环境不是"多一个碗"，是"多一套完整的厨房"——每个项目有自己的灶台、自己的调料架、自己的碗筷，互不干扰，各炒各的菜。

全局 Python 环境在项目规模小的时候，可以站起来蹬，一旦你需要和别人协作或者处理复杂的依赖，上车时座椅高度和你想要的不一样了。你的项目需要 `numpy==1.26`，隔壁项目需要 `numpy==2.0`，但只有一个位置，以谁为主呢？

## 从 `pyproject.toml` 到可运行环境

[工程化项目结构](./engineering_project_structure.md)我们写好了 `pyproject.toml`——这份文件定义了"项目是什么、依赖谁、怎么安装"。但它目前只是一份**声明**，就像一张写满食材的菜谱，还没真正下锅。

要把这份声明变成实际可运行的项目，还需要两步：

1. **创建一个独立的厨房**——虚拟环境，让项目有自己的独立空间
2. **按照菜谱采购食材**——用包管理工具安装 `pyproject.toml` 中声明的依赖

本章先讲虚拟环境（为什么要隔离、怎么隔离），再讲如何用工具把声明变成现实。

## 为什么需要隔离

Python 的导入机制本质是**在 `sys.path` 上按序搜索**。若所有项目共用同一个全局解释器：

- A 项目需要 `numpy==1.26`，B 项目需要 `numpy==2.0`，全局只能装一个版本，必有一方失败
- `pip install` 时可能因权限或系统包冲突把系统 Python 弄脏，回退困难
- "在我机器上能跑"往往是因为全局环境恰好有某依赖，而同事机器没有

虚拟环境要解决的正是**依赖的确定性与隔离性**：每个项目拥有独立的解释器、独立的 `site-packages`、独立的 `PATH`。

## 虚拟环境工具 vs 项目管理工具

在开始之前，先分清两个容易混淆的概念：

| 类型 | 工具 | 职责 |
|------|------|------|
| **虚拟环境工具** | `venv`、`conda`、`virtualenv` | 创建隔离的 Python 运行环境 |
| **项目管理工具** | `uv`、`poetry`、`pdm`、`hatch` | 管理依赖、构建、发布、锁文件等全流程 |

简单说：**虚拟环境工具管"在哪跑"，项目管理工具管"要什么、怎么装"**。

两者的关系是：用 `pyproject.toml` 声明项目需要什么，用虚拟环境提供隔离的运行空间，用包管理工具把声明安装到空间中。

## 三种主流方案

::::{tab-set}

:::{tab-item} venv + pip
```bash
# 创建虚拟环境
python -m venv .venv
# 激活（Linux/macOS）
source .venv/bin/activate
# 激活（Windows）
.venv\Scripts\activate
# 安装项目（可编辑模式）——读取 pyproject.toml
pip install -e .
# 或仅安装开发依赖
pip install -e ".[dev]"
# 退出
deactivate
```
:::

:::{tab-item} conda
```bash
# 创建环境并指定 Python 版本
conda create -n myproject python=3.12
# 激活
conda activate myproject
# 安装包（conda 优先）
conda install numpy pandas
# 混合使用 pip 安装 PyPI 专属包——同样读取 pyproject.toml
pip install -e .
```
:::

:::{tab-item} uv
```bash
# 初始化项目（自动生成 pyproject.toml 和 .venv）
uv init myproject
cd myproject
# 添加依赖（自动写入 pyproject.toml）
uv add numpy requests
# 添加开发依赖（自动写入 pyproject.toml 的 tool.uv 段）
uv add --dev pytest black
# 同步环境（读取 pyproject.toml，安装所有依赖）
uv sync
# 运行脚本
uv run python main.py
```
:::

::::


---

## 核心工作流：从 `pyproject.toml` 到可运行环境

无论选择哪种方案，核心步骤一致：

### 第一步：创建虚拟环境

::::{tab-set}

:::{tab-item} venv
```bash
mkdir myproject
cd myproject
python -m venv .venv
```
:::

:::{tab-item} conda
```bash
mkdir myproject
cd myproject
conda create -n myproject python=3.12
```
:::

:::{tab-item} uv
```bash
mkdir myproject
cd myproject
uv init && uv sync
```
:::

::::


### 第二步：安装项目本身

如果 `pyproject.toml` 中已经声明了项目元数据和依赖，现在要把"声明"变成"现实"：

::::{tab-set}

:::{tab-item} venv + pip
```bash
pip install -e .
```
:::

:::{tab-item} conda
```bash
conda activate myproject
# conda不支持从pyprojec.toml中创建环境，安装依赖，需要pydeps2env转换
conda install pydeps2env
pydeps2env pyproject.toml
conda env create -f environment.yml
```
:::

:::{tab-item} uv
```bash
uv sync
```
:::

::::

### 第三步：验证安装

安装成功后，可以在任意目录测试导入：

```bash
# 切换到任意目录（不在项目根目录）
cd /tmp
# 验证可以导入自己的包
python -c "import mypackage; print('导入成功')"
# 验证版本号与 pyproject.toml 一致
python -c "import mypackage; print(mypackage.__version__)"
```

如果这一步报 `ModuleNotFoundError`，说明 `pyproject.toml` 中的包配置有问题——最常见的原因是 `packages` 没有指向 `src/` 下的真实包路径。

---

## 虚拟环境隔离的本质

创建虚拟环境时，Python 做了三件关键事：

1. **复制或链接解释器**：在 `.venv/bin/python` 放置一个指向原解释器的副本或符号链接。
2. **独立的 `site-packages`**：`.venv/lib/python3.12/site-packages` 成为该环境独有的第三方包目录。
3. **改写 `sys.prefix` 与 `PATH`**：激活后 `sys.prefix` 指向虚拟环境根，`PATH` 首位加入 `.venv/bin`，使得 `python` 与 `pip` 优先解析到环境内。

未激活时，`sys.prefix` 与 `sys.base_prefix` 相等；激活后二者分离——这正是判断"是否在虚拟环境中"的可靠信号：

```python
import sys
print(sys.prefix)          # 当前环境路径
print(sys.base_prefix)     # 基础解释器路径
print(sys.prefix != sys.base_prefix)  # True 表示在虚拟环境中
```

---

**选型决策建议**

| 场景 | 推荐方案 | 优势 | 局限 |
|------|----------|------|------|
| 课程作业、简单项目 | `venv` + `pip` | 标准库自带，零额外安装；心智负担最小；与 `pyproject.toml` 原生配合 | 不管理 Python 版本；依赖解析慢；无锁文件保证一致性 |
| 数据科学、深度学习、原生依赖 | `conda` + `pip` | 能管理 Python 版本；能处理非 Python 原生依赖（CUDA、ffmpeg 等）；跨平台预编译包丰富 | 体积大（Miniconda 也有数百 MB）；解决器慢；部分 PyPI 新包需等 conda-forge 更新 |
| 团队协作、CI/CD | `uv` | 解析与安装比 `pip` 快 10–100 倍；自动管理虚拟环境；生成 `uv.lock` 保证依赖一致性；兼容 `pyproject.toml` | 较新（2024 年才稳定），需团队统一；部分老旧生态或内部 PyPI 镜像可能不兼容 |
| 已有 `requirements.txt` 的老项目 | `venv` + `pip install -r requirements.txt` | 无需改动现有工作流；迁移成本为零 | 无法利用 `pyproject.toml` 的元数据优势；依赖锁定靠手动 `pip freeze` |


