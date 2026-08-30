---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

# Shell 常见命令与用法

学完本节，你能回答：

- 为什么工程师需要掌握命令行，而不只是依赖图形界面？
- 文件系统、进程、管道三者如何协作完成复杂任务？
- 常用 Shell 命令（`grep`、`awk`、`find`、`xargs` 等）各自解决什么问题？

> Shell 是工程师的"第二编辑器"。理解文件系统、进程与管道，不是为了背命令，而是为了获得一种可组合的文本思维——把复杂任务拆成可串联的小工具。

在AI Agent能秒级生成复杂命令的今天，命令行成为了AI 与现实世界交流的链路。AI擅长翻译自然语言为命令序列，但它无法替你判断这条命令该在哪个目录执行、会不会覆盖重要文件、中间结果是否可恢复。脏活累活AI可以替你，但你得明白它每一步在做什么、为什么这么做。这一章虽讲“常见命令与用法”，目的不是背命令，而是让你在AI辅助编程的时代，依然保有对命令行的基础判断力。

## 文件和目录操作

| 命令 | 作用 | 示例 |
|------|------|------|
| `ls` | 列出目录内容 | `ls -lh data/uploads` 以易读格式显示文件大小 |
| `tree` | 树形显示目录结构 | `tree -L 2 src/` 限制显示深度为 2 层 |
| `cd` | 切换目录 | `cd /tmp` 切换到 tmp 目录 |
| `pwd` | 显示当前路径 | `pwd` 输出 `/home/user/project` |
| `mkdir` | 创建目录 | `mkdir -p data/temp/2024` 递归创建多级目录 |
| `touch` | 创建空文件或更新时间戳 | `touch config.py` 若文件不存在则创建 |
| `cp` | 复制文件或目录 | `cp -r src/ backup/` 递归复制目录 |
| `mv` | 移动或重命名 | `mv old.py new.py` 重命名文件 |
| `rm` | 删除文件或目录 | `rm -rf temp/` 强制递归删除（⚠️ 危险操作） |

## 文件内容查看

| 命令 | 作用 | 示例 |
|------|------|------|
| `cat` | 完整输出文件内容 | `cat pyproject.toml` 显示全部内容 |
| `head` | 查看文件开头部分 | `head -n 20 large.log` 查看前 20 行 |
| `tail` | 查看文件结尾部分 | `tail -f app.log` 实时跟踪日志输出 |
| `less` | 分页查看大文件 | `less data.csv` 用方向键滚动浏览 |

## 文本编辑器

在服务器或远程开发环境中，有时没有图形界面，需要直接在终端中编辑文件。`nano` 和 `vim` 是最常见的两种终端文本编辑器。

### `nano`：新手友好型编辑器

`nano` 界面简洁，底部有快捷键提示，适合快速编辑。

**打开文件**
```bash
nano config.py
```

**常用操作**

| 快捷键 | 作用 |
|--------|------|
| `Ctrl + O` | 保存文件（Write Out） |
| `Ctrl + X` | 退出编辑器 |
| `Ctrl + W` | 搜索文本 |
| `Ctrl + K` | 剪切当前行 |
| `Ctrl + U` | 粘贴（UnCut） |
| `Ctrl + /` | 跳转到指定行号 |
| `Alt + A` | 开始选择文本 |
| `Alt + 6` | 复制选中文本 |

### `vim`：高手的瑞士军刀

`vim`[^vimtutor] 是 `vi` 的改进版，以**模式编辑**著称，学习曲线陡峭但效率极高。它有三个核心模式：

| 模式 | 用途 | 如何进入 |
|------|------|----------|
| **普通模式**（Normal） | 移动光标、删除、复制、粘贴 | 默认进入，按 `Esc` 回到此模式 |
| **插入模式**（Insert） | 输入文本 | 按 `i`、`a`、`o` 等进入 |
| **命令模式**（Command） | 保存、退出、搜索、替换 | 按 `:` 进入 |

**打开文件**
```bash
vim config.py
```

**常用操作（普通模式下）**

| 操作 | 快捷键 | 说明 |
|------|--------|------|
| 删除 | `x` | 删除光标处字符 |
| 删除 | `dd` | 删除当前行 |
| 删除 | `d$` | 删除到行尾 |
| 复制 | `yy` | 复制当前行（yank） |
| 复制 | `yw` | 复制当前单词 |
| 粘贴 | `p` | 在光标后粘贴 |
| 撤销 | `u` | 撤销上一步操作 |
| 重做 | `Ctrl + r` | 重做撤销的操作 |

**命令模式操作（按 `:` 进入）**

| 命令 | 说明 |
|------|------|
| `:w` | 保存文件 |
| `:q` | 退出 |
| `:wq` 或 `:x` | 保存并退出 |
| `:q!` | 强制退出（不保存） |
| `:set nu` | 显示行号 |
| `:set nonu` | 隐藏行号 |
| `:%s/old/new/g` | 全局替换 old 为 new |

**快速上手 vim 的 5 个命令**：

| 命令 | 效果 |
|------|------|
| `i` | 进入插入模式（当前位置插入） |
| `Esc` | 回到普通模式（任何时候不知道做什么，按这个） |
| `:wq` | 保存并退出 |
| `:q!` | 放弃修改并退出 |
| `dd` + `p` | 剪切当前行并粘贴到下一行（快速移动代码行） |

至少学会一种终端编辑器。在远程服务器、Docker 容器、CI 环境等无图形界面的场景中，能直接修改文件是必备技能。初学者优先学 `nano`：5 分钟上手，够用。长期从事后端/运维的同学学 `vim`：初期有学习成本，但一旦形成肌肉记忆，代码编辑效率大幅提升，甚至于你可以配合vim的各种插件将其改造为足以媲美VS code的IDE。


## 重定向与管道

重定向和管道是 Shell 组合能力的核心：

**标准流**：每个进程有三个标准流
- `stdin`（0）：标准输入
- `stdout`（1）：标准输出
- `stderr`（2）：标准错误

```bash
# 重定向
python script.py > output.log      # stdout 写入文件（覆盖）
python script.py >> output.log     # stdout 追加到文件
python script.py 2> error.log      # stderr 单独写入文件
python script.py > all.log 2>&1    # stdout 和 stderr 合并到同一文件
python script.py 2>&1 | tee log    # 同时显示和保存

# /dev/null：丢弃输出
python script.py > /dev/null 2>&1  # 静默运行（不输出任何内容）
```

**管道 `|`**：将前一个命令的 `stdout` 作为后一个命令的 `stdin`

```bash
# 组合使用示例
# 1. 统计项目中 Python 文件行数并排序
find . -name "*.py" | xargs wc -l | sort -n | tail -5
# 2. 查看最耗内存的 5 个进程
ps aux --sort=-%mem | head -6
# 3. 统计日志中错误次数
grep "ERROR" app.log | wc -l
# 4. 查看 2024 年 3 月 15 日的日志
grep "2024-03-15" app.log | less
# 5. 提取 CSV 第二列并去重计数
cut -d',' -f2 data.csv | sort | uniq -c | sort -nr
```

## 文本编辑

有时需要在命令行中直接创建或追加文件内容，或者没有文本编辑器可用，以下是三种常用方式：

::::{tab-set}

:::{tab-item} echo+重定向
```bash
echo "hello world!" > .env          # > 覆盖写入
echo "hello world!" >> .env  # >> 追加到末尾
```
:::

:::{tab-item} cat+重定向
```bash
cat > config.sh << 'EOF'
hello world!
EOF
```
:::

:::{tab-item} echo+tee
```bash
echo "hello world!" | tee .env   # 写入文件并输出到终端
echo "hello world!" | tee -a .env  # -a 表示追加而非覆盖
```
:::

::::

## 进程管理

| 命令 | 作用 | 示例 |
|------|------|------|
| `ps` | 查看进程列表 | `ps aux | grep python` 显示所有进程并过滤 |
| `kill` | 终止进程 | `kill -9 12345` 强制终止 PID 为 12345 的进程 |
| `pkill` | 按名称终止进程 | `pkill -f uvicorn` 终止所有包含 uvicorn 的进程 |
| `top` / `htop` | 实时查看系统资源 | `top` 动态显示 CPU 和内存占用 |
| `jobs` | 查看后台任务 | `jobs -l` 列出后台进程及其 PID |
| `bg` / `fg` | 前后台切换 | `fg %1` 将后台任务 1 切回前台 |

```bash
# 后台运行服务
python -m myapp.cli serve &         # & 放到后台
python -m myapp.cli serve > app.log 2>&1 &  # 后台且输出到日志
# 进程查找与终止
ps aux | grep "myapp" | awk '{print $2}' | xargs kill -9
```

## 系统资源查看

| 命令 | 作用 | 示例 |
|------|------|------|
| `du` | 查看磁盘占用 | `du -sh data/` 显示 data 目录总大小 |
| `df` | 查看磁盘剩余空间 | `df -h /` 以易读格式显示根分区空间 |
| `free` | 查看内存使用 | `free -h` 以易读格式显示内存 |
| `bc` | 命令行计算器 | `echo "scale=2; 10/3" \| bc` 输出 3.33 |

## 文本处理与统计

| 命令 | 作用 | 示例 |
|------|------|------|
| `wc` | 统计行数、单词数、字符数 | `wc -l data.csv` 统计文件行数 |
| `grep` | 文本搜索 | `grep -r "ERROR" logs/` 递归搜索 ERROR |
| `awk` | 文本列处理 | `ps aux \| awk '{print $2, $11}'` 打印 PID 和命令列 |
| `sed` | 流编辑器（文本替换） | `sed 's/old/new/g' file.txt` 替换所有 old 为 new |
| `sort` | 排序 | `du -sh * \| sort -h` 按人类可读大小排序 |
| `uniq` | 去重 | `sort file.txt \| uniq -c` 统计重复次数 |
| `cut` | 提取列 | `cut -d',' -f1,3 data.csv` 提取第 1 和第 3 列 |
| `tr` | 字符替换或删除 | `cat file.txt \| tr '[:upper:]' '[:lower:]'` 转小写 |
| `xargs` | 将标准输入转为命令参数 | `find . -name "*.py" \| xargs wc -l` 统计所有 Python 文件行数 |

## `man`：命令行的一手文档

`man` 是 Linux/Unix 系统内置的**手册系统**，也是命令行最权威的“第一手文档”。当你忘记某个命令的选项、不确定参数含义时，`man ls` 会告诉你答案——不是二手解读，不是博客摘抄，而是该命令作者或维护者本人写下的原始说明。

`man` 页通常按章节组织（如第 1 章为普通命令、第 2 章为系统调用、第 3 章为库函数），最常用的是第 1 章。阅读时重点关注：

- **SYNOPSIS**：命令的基本格式，`[]` 表示可选参数，`<>` 表示必填参数
- **DESCRIPTION**：命令的功能说明，通常会解释核心逻辑
- **OPTIONS**：各选项的详细说明，按字母或功能分组

浏览时可用 `/` 搜索关键词，按 `n` 跳到下一个匹配，按 `q` 退出[^vimop]。不必从头读到尾，把它当作工具书来查——知道它存在、知道怎么翻到需要的那一页，就够了。

## Makefile：任务自动化

Makefile 本质上是一个**任务脚本集合**，用于把频繁操作（运行、测试、清理、部署）固化为可记忆的命令。

```makefile
# Makefile
.PHONY: help install test clean

install:           # 安装依赖
    pip install -e ".[dev]"

test:              # 运行测试
    pytest tests/ -v

clean:             # 清理临时文件
    rm -rf .pytest_cache/ .mypy_cache/
    find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null

serve:             # 启动服务
    python -m myapp.cli serve --port 8000

lint:              # 代码检查
    ruff check .
    mypy src/

format:            # 代码格式化
    black src/ tests/

all: lint test     # 默认任务
```

使用方式：
```bash
make install      # 安装依赖
make test         # 运行测试
make serve        # 启动服务
make clean        # 清理缓存
make              # 不指定则执行第一个任务（all）
```


[^vimtutor]:[菜鸟教程 vi/vim](https://www.runoob.com/linux/linux-vim.html)，或者使用`vimtutor`命令
[^vimop]: man中的各种操作与vim的操作方法一致
