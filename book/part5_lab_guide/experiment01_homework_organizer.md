# 课程作业整理工具

## 实验目标

通过完成一个课程作业整理工具，你将：

1. **掌握 Git 协作工作流**：使用分支开发、提交管理、PR 流程
2. **理解 Python 工程化结构**：使用 `uv` 管理依赖和项目元数据
3. **编写可用的工程脚本**：综合运用 `argparse`、`pathlib`、`shutil`、`subprocess`、`openpyxl`
4. **使用 Makefile 自动化**：将常用操作固化为可记忆的命令

## 背景故事

你是一个班级的助教。期末考试结束了，同学们通过网盘或邮箱提交了课程作业。你下载了全班 20 位同学的作业，文件命名五花八门：

```
作业1.pdf
张三的作业.pdf
exp3_李四.zip
王五-实验报告.docx
作业_final_赵六.pdf
...
```

同时你有一份 Excel 选课名单待生成（见“辅助工具”一节），你的任务是：**按名单把 20 份作业重命名为统一格式，再按班级分类存放**。

## 辅助工具：生成 20 份作业与统计表

本工具由教师提供[generate_roster.py](../../labs/lab01_project_init/generate_roster.py)，用于生成后续整理所需的数据，直接运行即可，无需实现。

```bash
python tools/generate_roster.py --output data/roster.xlsx --source data/source --seed 42
```

## 项目需求

**核心功能**：

- 读取 `roster.xlsx`，按表头名定位 `学号` / `姓名` / `班级` 三列，建立 `姓名 → 学号、班级` 映射；基于整理结果**回填** `原始作业文件名` / `修改后作业文件名` 两列
- 将匹配到的文件重命名为 `学号_姓名_班级.扩展名`（学号取自表格）并按班级创建子目录移动；未匹配的文件归入 `未识别/`
- 支持 `--dry-run` 模式（仅预览，不实际执行；不写文件、不改表）
- 仅暴露 4 个 CLI 参数：`--roster`、`--source`、`--output`、`--dry-run`（另含自动 `--help`）

**示例 Excel 格式**（`roster.xlsx`，由生成工具产出）：

| 学号 | 姓名 | 班级 | 原始作业文件名 | 修改后作业文件名 |
|------|------|------|---------------|-----------------|
| 26104101 | 张三 | 1 |  |  |
| 26104202 | 李四 | 2 |  |  |
| 26104103 | 王五 | 1 |  |  |

## 实验步骤

### 第一步：初始化项目

```bash
# 1. 创建项目目录
mkdir homework-organizer
cd homework-organizer
# 2. 使用 uv 初始化项目
uv init
# 3. 添加依赖
uv add openpyxl
# 4. 创建 .gitignore
vim .gitignore
# 5. 首次提交
git add .
git commit -m "chore: initial project setup"
```

### 第二步：创建项目结构

### 第三步：实现核心脚本

在 `./main.py` 中实现以下功能：

```python
#!/usr/bin/env python3
"""
课程作业整理 - 根据 Excel 名单重命名作业文件

Usage:
    python -m homework_organizer.organizer --roster data/roster.xlsx --source data/source --output data/output
    python -m homework_organizer.organizer --roster data/roster.xlsx --source data/source --output data/output --dry-run
"""

import argparse
import shutil
from pathlib import Path
from openpyxl import load_workbook
from src.tools import load_roster, organize_homework

def parse_args():
    parser = argparse.ArgumentParser(description="作业整理工具")
    parser.add_argument("--roster", required=True, help="Excel 选课名单路径")
    parser.add_argument("--source", default="data/source", help="作业源目录")
    parser.add_argument("--output", default="data/output", help="输出目录")
    parser.add_argument("--dry-run", action="store_true", help="仅预览，不实际执行")
    return parser.parse_args()

def main():
    args = parse_args()
    roster = load_roster(Path(args.roster))
    stats = organize_homework(
        Path(args.source),
        Path(args.output),
        roster,
        args.dry_run
    )
    print(f"处理完成: {stats}")


if __name__ == "__main__":
    main()
```

### 第四步：使用 Git 分支开发

```bash
# 1. 从 main 创建功能分支
git switch -c feat/organize-homework

# 2. 每个功能点独立提交，例如
git add src/homework_organizer/organizer.py
git commit -m "feat: add argparse CLI interface"
...

# 3. 修复 bug
git add src/homework_organizer/organizer.py
git commit -m "fix: handle file extensions correctly"

# 4. 查看提交历史
git log --oneline -5

# 5. 合并回 main
git switch main
git merge feat/organize-homework
```

### 第五步：编写 Makefile

```makefile
# Makefile
.PHONY: help install generate run clean

help:
	@echo "可用命令:"
	@echo "  make install  - 安装依赖"
	@echo "  make generate - 生成 20 份作业与 roster.xlsx"
	@echo "  make run      - 运行作业整理脚本"
	@echo "  make clean    - 清理临时文件"

install:
	uv sync

run:
	python -m homework_organizer.organizer \
		--roster data/roster.xlsx \
		--source data/source \
		--output data/output

clean:
	rm -rf __pycache__ .pytest_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null
```

### 第六步：测试运行

```bash
# 安装依赖
make install
# 预览模式
python -m homework_organizer.organizer --roster data/roster.xlsx --source data/source --output data/output --dry-run
# 正式运行
make run
# 查看归档结果
tree data/output
```

`--help` 校验：

```bash
python -m homework_organizer.organizer --help
# 应显示 --roster --source --output --dry-run 四项
```

### 第七步：提交 PR

```bash
# 1. 推送功能分支
git push -u origin feat/organize-homework

# 2. 在 GitHub/GitLab 上创建 Pull Request
#    - 标题: feat: 实现课程作业整理工具
#    - 描述: 按 Excel 名单自动重命名为 学号_姓名_班级 并分类

# 3. PR 通过后合并
git switch main
git pull
git branch -d feat/organize-homework
git push origin --delete feat/organize-homework
```

## 验收标准

| 验收项 | 具体要求 |
|--------|----------|
| **项目结构** | 使用 `src/` 布局，`pyproject.toml` 完整，依赖通过 `uv add` 添加 |
| **核心功能** | 能正确读取 Excel、按姓名匹配文件、按表格学号重命名为 `学号_姓名_班级.扩展名` 并按班级分类，且**回填** `roster.xlsx` 的 `原始作业文件名` / `修改后作业文件名` 两列 |
| **参数支持** | 仅 `--roster`、`--source`、`--output`、`--dry-run`、`--help`，无多余参数 |
| **表头定位** | 定位“学号/姓名/班级” |
| **未识别处理** | 无法匹配的文件放入 `未识别/` 目录，并在 roster 中对应行留空或标记 |
| **Git 历史** | 提交粒度合理，提交信息符合约定式规范 |
| **Makefile** | `make install`、`make run`、`make clean` 可用（`make generate` 为复用教师工具，非必实现） |

## 提交要求

**1. 代码提交**：

- 将代码推送到你的 GitHub/Gitee 仓库
- 在 `README.md` 中说明学号规则与使用方式

**2. PR 说明**（在 PR 描述中填写）：

```
# 功能说明
- 按 8 位学号重命名为 学号_姓名_班级.pdf/docx/zip 并按班级分类
- 正确回填 roster.xlsx 的 原始作业文件名 / 修改后作业文件名 两列
- 支持 --dry-run 预览、--help 帮助

# 使用方式
python -m homework_organizer.organizer --roster data/roster.xlsx --source data/source --output data/output --dry-run
python -m homework_organizer.organizer --roster data/roster.xlsx --source data/source --output data/output

# 自测结果
- [x] 正确读取 20 行 roster，按表头名定位
- [x] 重命名符合 8 位规则且回填后两列一一对应
- [x] --dry-run 只预览不执行
- [x] --help 仅显示 4 参数
- [x] 未识别文件放入未识别目录

# 运行记录
贴上 tree 输出
```
