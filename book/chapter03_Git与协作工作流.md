---
jupytext:
  text_representation:
    extension: .md
    format_name: myst
    format_version: '0.13'
    jupytext_version: 1.16.4
kernelspec:
  display_name: Python 3
  language: python
  name: python3
---

# 第3章 Git 与协作工作流

> 为什么学 Git？因为从本章起，你不再是「单人写脚本」，而是「多人改同一仓库」。没有分支与提交规范，两个人同时改一个文件就会互相覆盖；没有 PR（Pull Request）流程，代码质量全靠自觉。本章以本书仓库 `eng-practice-book` 为演练场，完成你的首次特性分支（feature branch）协作闭环：从提交、分支、推送到 PR 与冲突解决。学完本章，你能用分支隔离改动、用 PR 发起协作、用正确姿势解决冲突——并理解 MeetingToText 的协作约定为何这样设计。

## 学习目标

完成本章后，你将能够：

1. 能解释「提交（commit）是快照而非补丁」与「分支是指针」的含义，并用 `git log --oneline --graph` 读懂历史图。
2. 能按「特性分支 → 提交 → 推送 → PR」流程在本书仓库内完成一次完整协作演练。
3. 能复现并解决一次 `merge` 冲突，正确解读 `<<<<<<<` / `=======` / `>>>>>>>` 冲突标记块。
4. 能区分 `git revert` 与 `git reset` 对历史的影响，并选择不改写已推送历史的安全方式撤销改动。
5. 能对照 MeetingToText `CONTRIBUTING.md` 的协作约定，解释「日志英文、用户提示中文、配置单一事实源」等约定的协作价值。

## 先修要求

- 已完成第1章「工程环境与项目骨架」，能在本机克隆并 `jupyter-book build`。
- 会用命令行执行 `git status` / `git log` / `git diff` 基础查看命令。
- 已配置 `git config --global user.name` 与 `user.email`（PR 会显示此身份）。

## 正文

### 3.1 提交（commit）：最小可审查单元

Git 的提交不是「改动了哪几行」的补丁（patch），而是「整个工作区在这一刻的快照（snapshot）」加一个指向父提交的指针。连续提交形成一条有向无环图（DAG），`git log` 看到的直线只是 DAG 的一种拓扑展示。

最常用的提交相关命令：

```bash
git status                          # 看工作区与暂存区状态
git diff                            # 工作区 vs 暂存区差异
git diff --cached                   # 暂存区 vs HEAD 差异
git add {文件路径}                  # 将改动加入暂存区（stage）
git commit -m "docs(chapter03): add feature branch demo"
git log --oneline --graph --all -n 10
```

提交信息遵循 Conventional Commits（与本书 Commit strategy 一致）：`type(scope): subject`，如 `docs(chapter03): ...` / `feat(m2t): ...`。一个提交只做一件事、只改一个关注点，是「最小可审查单元」——评审者可以逐提交理解意图，回滚时也能精确撤销。

用 Python 解析 `git log --oneline` 文本，提取提交信息结构（可运行）：

```{code-cell} ipython3
import re

sample_log = """\
a1b2c3d docs(chapter03): add feature branch demo
e4f5a6b docs(chapter01): full environment-and-skeleton chapter as style anchor
c7d8e9f chore: initialize book repository skeleton
"""

commit_re = re.compile(r"^(?P<hash>[0-9a-f]{7,40})\s+(?P<type>\w+)(?:\((?P<scope>[^)]+)\))?:\s*(?P<subject>.+)$")

def parse_git_log(lines: list[str]) -> list[dict]:
    """解析 git log --oneline 文本为结构化记录（习题也会复用此模式）。"""
    out: list[dict] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        m = commit_re.match(line)
        if m:
            out.append(m.groupdict())
        else:
            out.append({"hash": line.split()[0], "type": "", "scope": "", "subject": line})
    return out

for rec in parse_git_log(sample_log.splitlines()):
    print(rec)
```

**要点**：`parse_git_log` 把人类可读的日志文本变成机器可断言的结构，这正是习题用 hermetic Python 题「模拟 git」而非依赖真实仓库状态的原因——文本解析确定、可重复、可 pytest。

### 3.2 分支（branch）：可移动的指针

分支在 Git 中只是一个指向某次提交的可移动指针（`refs/heads/{分支名}`），创建与切换成本极低。`HEAD` 指向当前分支，提交时分支指针与 `HEAD` 一起前移。

```bash
git branch                          # 列出本地分支，* 标记当前分支
git switch -c feature/chapter03-demo  # 创建并切换到特性分支（等价于 git checkout -b）
git branch -v                       # 看每个分支指向的提交
git log --oneline --graph --all    # 看分支分叉与合并的图结构
```

在 Python 中模拟提交图（commit DAG），理解「分支是指针」：

```{code-cell} ipython3
# 极简提交图：每个提交存 parent 指针，分支存指向提交的 id
commits = {
    "c0": {"parents": [], "msg": "chore: init"},
    "c1": {"parents": ["c0"], "msg": "docs(chapter01): style anchor"},
    "c2": {"parents": ["c1"], "msg": "feat: add chapter03 demo on main"},
    "c3": {"parents": ["c1"], "msg": "feat: add chapter03 demo on feature/chapter03-demo"},
    "c4": {"parents": ["c2", "c3"], "msg": "Merge feature/chapter03-demo into main"},
}
branches = {"main": "c2", "feature/chapter03-demo": "c3"}

def ancestors(commit_id: str) -> set[str]:
    seen, stack = set(), [commit_id]
    while stack:
        cur = stack.pop()
        if cur in seen:
            continue
        seen.add(cur)
        stack.extend(commits[cur]["parents"])
    return seen

def is_ancestor(anc: str, desc: str) -> bool:
    return anc in ancestors(desc)

print("c1 是 c2 的祖先？", is_ancestor("c1", "c2"))
print("c2 是 c3 的祖先？", is_ancestor("c2", "c3"))
print("c1 是 c4 的祖先？", is_ancestor("c1", "c4"))
print("分支 main 指向", branches["main"], "feature 指向", branches["feature/chapter03-demo"])
# 合并后 main 会前移到 c4（merge commit 有两个 parent）
branches_after_merge = {"main": "c4"}
print("合并后 main 指向", branches_after_merge["main"], "parents:", commits["c4"]["parents"])
```

**规则**：

- `main` 分支保持可构建（`jupyter-book build --execute` 绿）；所有改动先在 `feature/*` 分支上验证。
- 分支命名用 `feature/` / `fix/` / `docs/` 前缀，如 `feature/chapter03-demo`、`docs/chapter03`，见名知意。
- 已推送的 `main` 历史不改写（不用 `git push --force` 重写公共历史），撤销用 `revert` 而非 `reset`。

### 3.3 协作：PR 流程——在本书仓库做首次特性分支演练

本节是本章的**应用演练**：在 `eng-practice-book` 仓库内走通一次真实的特性分支协作。以下步骤在本书仓库根目录执行，假设远端为 `origin`、主分支为 `main`。

```bash
# 0) 确认工作区干净（只读门前置）
git status --porcelain | wc -l   # 期望 0

# 1) 从最新 main 切特性分支
git switch main
git pull --ff-only
git switch -c feature/chapter03-demo

# 2) 做改动并提交（示例：在 book/chapter03_*.md 中加一行注释）
echo "<!-- chapter03 demo -->" >> book/chapter03_Git与协作工作流.md
git add book/chapter03_Git与协作工作流.md
git commit -m "docs(chapter03): demo feature branch commit"

# 3) 推送特性分支
git push -u origin feature/chapter03-demo

# 4) 在 GitHub 发起 PR：feature/chapter03-demo -> main，填写标题与描述，请求评审
#    评审通过后 Squash 或 Merge 合并，删除特性分支

# 5) 回到 main 并同步
git switch main
git pull --ff-only
git branch -d feature/chapter03-demo
git log --oneline --graph --all -n 8
```

**PR（Pull Request）的协作价值**：

- **异步评审**：改动在合并前可被他人阅读、评论、要求修改，避免「直接推 main」绕过质量门。
- **CI 门控**：PR 可关联 `jupyter-book build --execute` 与 `pytest answers/chapter03/ -q` 等检查，未绿不合入。
- **可追溯**：PR 标题与描述成为变更的上下文，比单行 commit message 更易理解「为什么」。

> 提示：本书仓库当前为本地私有、未设远端推送（见计划决策⑦），课堂演练可用本机多克隆或在个人 fork 上完成上述流程，命令与协作语义完全一致。

### 3.4 冲突（conflict）：复现、读懂、解决

当两个分支改了同一文件的同一区域，`git merge` 无法自动决定以谁为准，会停在冲突状态，让你手动选择。

复现一次最小冲突：

```bash
# 准备：从同一基点分叉
git switch -c feature/a main
echo "line: hello from a" > /tmp/demo.txt
git add /tmp/demo.txt && git commit -m "feat: add line from a"
git switch main
echo "line: hello from main" > /tmp/demo.txt
git add /tmp/demo.txt && git commit -m "feat: add line from main"

# 合并 feature/a -> main，触发冲突
git merge feature/a
# 输出类似：CONFLICT (content): Merge conflict in /tmp/demo.txt
#          Automatic merge failed; fix conflicts and then commit the result.

# 查看冲突标记
cat /tmp/demo.txt
# <<<<<<< HEAD
# line: hello from main
# =======
# line: hello from a
# >>>>>>> feature/a

# 解决：编辑文件保留期望内容，删除标记行
# 手动编辑 /tmp/demo.txt 为最终期望内容，例如：
# line: hello merged

# 标记已解决并完成合并
git add /tmp/demo.txt
git commit -m "Merge feature/a into main (resolve conflict)"

# 或放弃合并
# git merge --abort
```

**如何读冲突块**：

- `<<<<<<< HEAD` 到 `=======` 之间是当前分支（`HEAD`，即 `main`）的内容。
- `=======` 到 `>>>>>>> feature/a` 之间是被合入分支的内容。
- 解决冲突不是「二选一」，而是「写出正确的最终文件」——可能取其一、可能两者融合、可能重写。

**避免冲突的协作习惯**：

- 小步提交、频繁 `git pull --rebase` 或 `git merge main` 同步主线。
- 按文件职责分工，减少多人同时改同一段落。
- 合并前 `git diff main...feature/a` 预览差异。

### 3.5 撤销：revert vs reset

| 操作 | 是否改写历史 | 是否影响已推送分支 | 适用场景 |
|---|---|---|---|
| `git revert {commit}` | 否（新增一次「反向提交」抵消目标提交） | 安全 | 已推送到远端的提交需要撤销 |
| `git reset --hard {commit}` | 是（移动分支指针、丢弃其后提交） | 危险，需 `--force` | 仅本地未推送的历史整理 |

```bash
# 安全撤销：为已推送的错误提交生成反向提交
git log --oneline -n 5
git revert {错误提交的hash}
# 编辑器会生成默认信息 "Revert \"...\"", 保存即完成
git log --oneline -n 5   # 多了一次 revert 提交，原错误提交仍在历史中

# 危险操作：仅在本地未推送时使用
# git reset --hard HEAD~1   # 回到上一次提交，丢弃当前提交（工作区也会丢失）
# git restore --source=HEAD -- {文件}  # 丢弃工作区对某文件的未暂存改动
```

**原则**：公共历史（已 `push` 的 `main`）只用 `revert` 撤销；`reset` / `rebase -i` 只用于本地未推送的分支整理，整理完再 `push`。

### 3.6 协作约定范例：对照 MeetingToText `CONTRIBUTING.md`

本书以 MeetingToText 的 `CONTRIBUTING.md` 为协作约定范例（只读对照，不复制源码）。其要点可直接映射到本章的协作流程：

1. **语言与消息规范**：日志（`logger.*`）一律英文，用户可见的校验错误与业务异常用中文；已知例外需在表格中登记。这解释了为何提交信息与日志用英文、而 PR 描述与用户文档用中文——前者面向机器检索，后者面向中文用户。
2. **配置单一事实源**：所有用户可设置的配置项定义在 `backend/app/config.py` 的 `SETTING_SPECS` 字典，读写需遵守 `settings_lock` 契约。协作中「单一事实源」避免多人各写各的配置表。
3. **教学阅读顺序**：`CONTRIBUTING.md` 给出 14 步代码阅读路径（从 `frontend/src/utils/*` 纯函数到 `routers/record.py` 最复杂单文件），新成员按此路径递增理解，避免一开始就跳入最复杂模块。
4. **部署安全要点**：默认绑定 `127.0.0.1`、密钥明文落盘风险与缓解（环境变量优先于 DB、`GET /api/settings` 脱敏），说明协作约定不仅管代码风格，也管安全边界。

> 延伸：协作约定应落在仓库根的 `CONTRIBUTING.md` / `README.md` 并被 CI 引用，而非口头约定。本书仓库的 `book/STYLE.md` 即承担此角色。

### 改动并预测

以下 3 个实验均可在本地临时仓库（`tmp_path` + 真 `git`）或本书仓库的特性分支上复现。每个实验按「改什么 → 预测 → 解释」三段式书写。

#### 改动并预测 实验 1：同一文件同一行分叉修改后 merge → 预测冲突标记块

- **改什么**：从同一基点切出 `feature/a` 与 `main` 两个分支，分别把同一文件的同一行改为不同内容（如 `line: hello from a` vs `line: hello from main`），然后在 `main` 上执行 `git merge feature/a`。
- **预测**：`git merge` 退出非零，提示 `CONFLICT (content): Merge conflict in {文件}`，`git status` 显示 `both modified: {文件}`；打开文件会看到三段式冲突标记：
  ```
  <<<<<<< HEAD
  line: hello from main
  =======
  line: hello from a
  >>>>>>> feature/a
  ```
  此时 `git commit` 被阻塞，必须先编辑文件解决冲突、`git add` 标记已解决后才能完成合并。
- **解释**：Git 以行为单位做三路合并（merge base → HEAD → 被合入分支），同一区域的并发修改无唯一正确解，Git 选择停下来让人决策。`HEAD` 侧是当前分支内容，`>>>>>>>` 侧是被合入分支内容，`=======` 为分界。解决冲突的本质是「写出正确的最终文件」，而非机械二选一。

#### 改动并预测 实验 2：对已推送提交执行 git revert → 预测历史节点变化

- **改什么**：在 `main` 上做一次提交 `c_bad`（如改错一行配置），`git push` 后执行 `git revert c_bad` 并完成提交，观察 `git log --oneline --graph -n 5`。
- **预测**：历史多一个新提交 `c_revert`，其信息默认为 `Revert "c_bad 的 subject"`，`git log` 显示 `c_bad` 仍在原位、`c_revert` 在其后；`git show c_revert` 的 diff 恰好是 `c_bad` 的反向补丁；工作区文件回到 `c_bad` 之前的状态。
- **解释**：`revert` 不改写历史，而是新增一次「抵消提交」来保持 DAG 的不可变性——这对已推送的公共历史是安全的。`reset --hard` 会移动分支指针并丢弃 `c_bad`，需要 `push --force` 才能同步远端，会让已拉取该历史的协作者产生分叉，故公共分支禁用。

#### 改动并预测 实验 3：工作区有未暂存改动时执行 git restore / git checkout -- → 预测文件内容

- **改什么**：修改某已跟踪文件（如在 `book/chapter03_Git与协作工作流.md` 末尾加一行 `TEMP`），不 `git add`，分别试验 `git diff` 能看到改动，然后执行 `git restore --source=HEAD -- {文件}`（或 `git checkout -- {文件}`），再看文件内容与 `git status`。
- **预测**：`git restore` 后文件内容回到 `HEAD` 版本，`TEMP` 行消失，`git status` 变干净（`working tree clean`），且 `git log` 完全不变（历史未动）；若改动已 `git add` 但未 commit，则需 `git restore --staged {文件}` 先取消暂存，再 `git restore --worktree {文件}` 丢弃工作区改动。
- **解释**：Git 有三棵树：`HEAD`（已提交快照）、index/暂存区、`worktree`（工作区）。`restore --source=HEAD --worktree` 是用 `HEAD` 的快照覆盖工作区，未提交的改动被丢弃且不可恢复（除非有编辑器备份）。这验证了「未提交的改动不属于历史、无安全网」的协作纪律——重要改动及时 `commit`，丢弃前先 `git diff` 确认。

## 习题

> 参考答案与测试在 `answers/chapter03/`，运行 `pytest answers/chapter03/ -q` 验证。题目优先用 `tmp_path` + `subprocess` 真 `git` 做断言；若环境 `git` 不可靠，退化为 hermetic Python 题（`parse_git_log` 等）。

1. **解析 git log**：实现 `parse_git_log(lines: list[str]) -> list[dict]`，解析 `git log --oneline` 文本（每行 `"{hash} {type}({scope}): {subject}"` 或 `"{hash} {subject}"`），返回结构化记录，未匹配的行仍保留 `hash` 与 `subject`。
2. **分支名前缀校验**：实现 `is_valid_branch_name(name: str) -> bool`，校验分支名符合 `feature/` / `fix/` / `docs/` / `chore/` 前缀且后缀非空、仅含小写字母数字与 `-` `_` `/`。
3. **冲突标记检测**：实现 `has_conflict_markers(text: str) -> bool`，判断文件文本是否含 Git 冲突标记（`<<<<<<< ` / `=======` / `>>>>>>> ` 行）。
4. **revert 提交识别**：实现 `is_revert_commit(subject: str) -> bool`，判断提交标题是否为 `revert` 提交（`Revert "..."` 前缀，大小写不敏感，允许 `revert:` 冒号形式）。
5. **提交图祖先判断**：实现 `is_ancestor(graph: dict[str, list[str]], anc: str, desc: str) -> bool`，给定提交图（`{commit: [parents]}`）判断 `anc` 是否为 `desc` 的祖先（含传递闭包，`anc == desc` 视为是）。
6. *（附加·真 git）* 在 `tmp_path` 建临时仓库，分别在 `main` 与 `feature/a` 上改同一文件同一行后 `merge`，断言 `git status` 含 `both modified` 且文件含 `<<<<<<<`。

## 延伸挑战

1. 在本书仓库内按 3.3 节做一次真实特性分支演练：切 `feature/chapter03-{学号}` 分支，改动任意一章的错别字，推送并在 GitHub 上发起 PR，观察 CI（`jupyter-book build --execute`）的门控效果。
2. 对比 `git merge --no-ff` 与 `git merge --ff-only`：分别在两种模式下合并同一特性分支，用 `git log --oneline --graph` 记录历史图差异，解释何时需要保留 merge commit。
3. 用 `git rebase -i HEAD~3` 整理本地未推送的 3 次提交（合并 fixup、重写 message），对比 `rebase` 与 `merge` 对历史线性度的影响，并说明为何已推送历史禁用 rebase。
4. 阅读 MeetingToText `CONTRIBUTING.md` 的「已知例外」表格，尝试为本书仓库的 `book/STYLE.md` 设计一张类似的「协作例外登记表」，列出你认为需要例外的场景与理由。

## 附录（选学）：git hooks 自动化检查

> 本附录为选学内容，不作为正文必修；本仓库不预置任何 `.git/hooks/` 或 `husky` 配置，是否启用由读者按需决定。

Git hooks 是在特定 Git 事件前后自动触发的本地脚本（如 `pre-commit` 在提交前、`pre-push` 在推送前执行）。常见用途是在本地拦截低级错误：提交前跑 `ruff` / `mypq` / `pytest`、检查提交信息是否符合 Conventional Commits、阻止大文件误提交。

启用一个最小 `pre-commit` 示例（需手动创建，仓库不预置）：

```bash
# 在 eng-practice-book 仓库根执行（选学，按需手动创建）
cat > .git/hooks/pre-commit <<'HOOK'
#!/usr/bin/env bash
set -e
echo "[hook] running ruff check ..."
ruff check .
echo "[hook] running pytest answers/chapter03 -q ..."
pytest answers/chapter03 -q
HOOK
chmod +x .git/hooks/pre-commit

# 下次 git commit 时会自动执行上述检查；绕过用 git commit --no-verify
```

进阶可选 `pre-commit` 框架（`pip install pre-commit` + `.pre-commit-config.yaml`）或前端 `husky`，但均属选学工具链——本章不预置、不强制，未安装时协作流程完全可用；启用后也可用 `--no-verify` 按需绕过，避免阻塞紧急提交。
