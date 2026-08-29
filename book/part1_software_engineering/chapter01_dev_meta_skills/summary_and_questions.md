---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

## 本章小结

- **工程化项目结构是协作的起点**：`src` 布局通过物理隔离暴露导入与打包问题，`pyproject.toml` 以 PEP 517/518/621 统一构建与元数据，二者共同构成“可安装、可测试”的最小工程契约。以通用项目 `myproject` 为例，`src/mypackage` 与声明式描述共同避免了“根目录即包”的歧义。
- **依赖与虚拟环境的本质是隔离**：`venv` / `conda` / `uv` 的差异在于“是否管理 Python 版本与原生依赖”以及“解析速度”，选型应基于项目特征而非偏好；隔离的本质是独立的解释器、`site-packages` 与 `sys.prefix`，激活与否可通过 `sys.prefix != sys.base_prefix` 可靠判断。
- **Shell 的核心是可组合的文本流水线**：文件系统提供统一的路径抽象，进程提供隔离的执行上下文，管道提供“单件工具 + 文本流”的组合能力；`pathlib` / `subprocess` / 生成器表达式可用 Python 复刻这些思想，便于在脚本与 CI 中保持一致行为。
- **自动化脚本把操作变成代码**：`subprocess` 负责进程调用（避免 `shell=True`）、`shutil` 负责可移植文件操作、`argparse`（或 `click`）负责命令行封装；“参数解析与业务逻辑分离”是脚本可测试的关键。
- **Git 工作流让协作可预期**：用分支隔离并行开发、用小步提交让历史可读、用 PR 承载 Review 与 CI 校验；`Git Flow` 适合多版本并行，`GitHub Flow` 适合持续交付，选择取决于发布节奏与团队规模，而非技术潮流。
- **贯穿启示**：本章所有能力共同服务于“可复现、可协作、可审计”的工程底座；后续章节的质量门禁、测试、容器化与 CI/CD 都建立在这一底座之上。

## 思考题

1. **布局取舍**：在什么情况下你会选择扁平布局而非 `src` 布局？如果项目同时包含 Python 与前端代码（`frontend/`），`pyproject.toml` 的 `packages` 字段应如何配置以避免误打包？
2. **隔离边界**：虚拟环境隔离了 `site-packages`，但未隔离系统库与环境变量。结合通用 `APP_DATA_DIR` 与模型缓存等外部配置的用法，讨论“环境隔离”与“配置外置”的边界应如何划分。
 3. **管道与函数**：Shell 管道 `find | xargs | sort` 与 Python 的生成器管道各有何优劣？在一个“上传 → 预处理 → 分析 → 导出”四段流水线中，哪一段更适合用管道思维，哪一段更适合用函数调用？可结合“上传 → 切片 → 转写 → 纪要”的流水线对照思考。
4. **自动化粒度**：`Makefile` 与 Python 脚本在自动化中的分工应如何界定？当一个自动化任务需要在不同 Linux 环境（本机、CI、服务器）间保持一致时，你会如何决定用 `Makefile`、`Shell` 还是 `Python` 实现？
5. **Git 工作流演进**：假设一个单人课程项目演进为 10 人团队的持续交付产品，你会如何从 GitHub Flow 逐步引入 `release` 分支或 feature flag？分支策略的变更会对 CI 流水线与发布流程带来哪些连锁影响？
6. **提交粒度的启发**：Git 提倡“一个提交只做一件事”以便回退与 Review，`m2t.store.TaskStore` 用 SQLite 做任务持久化。能否为任务设计类似的“小步快照”机制？这种机制会如何影响“任务回滚”与“审计追溯”能力？
7. **工具选型**：`uv` 声称比 `pip` 快 10–100 倍，但引入新工具也有学习与迁移成本。结合你所在团队的 CI 时长与成员熟悉度，讨论何时值得引入 `uv`，何时应保持 `venv + pip` 的简单方案。

示例（本章贯通校验：用教学包串联“存储 → 导出”最小闭环）：

```{code-cell} ipython3
import tempfile, pathlib
from m2t.store import TaskStore
from m2t.export import export

with tempfile.TemporaryDirectory() as td:
    db = pathlib.Path(td) / "summary.db"
    store = TaskStore(db)
    # 1) 存储：通用任务创建（此处以教学包 m2t 为例）
    store.create("s1", "demo.wav", full_text="本章讲述环境、脚本与协作")
    task = store.get("s1")
    print("stored:", task["filename"], task["status"])

    # 2) 导出：复用 m2t.export 的纯函数能力（与存储解耦）
    fake_task = {
        "id": task["id"],
        "filename": task["filename"],
        "result": {
            "duration": 10,
            "segments": [{"speaker": "说话人1", "text": task["full_text"], "start": 0, "end": 2}],
        },
        "minutes": "要点：环境隔离、管道组合、分支协作",
    }
    md = export(fake_task, "md")
    print(md.splitlines()[0])
    assert "demo.wav" in md
    print("闭环校验通过：store -> export 可独立测试与组合")
# 预期输出:
# stored: demo.wav pending
# # 会议转录
# 闭环校验通过：store -> export 可独立测试与组合
```
