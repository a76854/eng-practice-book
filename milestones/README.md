# 里程碑评测约定（Grader Convention）

> 6.031 模式（双反向验证）：好解通过、故意做错的解被判失败、且“学生的测试套件”必须能捉住错解——防止空测试集“恒通过”的虚假评分。

## 1. 目录约定

每个里程碑位于 `milestones/<name>/`，固定三目录：

```
milestones/<name>/
  student_solution/    # 学生提交的代码（被测对象）
  tests/               # 黑盒测试（唯一判分依据；由教师维护，对学生只读）
  reference_solution/  # 教师参考解（自检与对照；不参与判分）
```

| 目录 | 谁写 | 用途 |
|------|------|------|
| `student_solution/` | 学生 | `run_grader` 默认的被测目录 |
| `tests/` | 教师 | 权威测试集；黑盒，只通过公开接口测行为，不窥探实现 |
| `reference_solution/` | 教师 | 已知正确的实现，用于验证 `tests/` 本身有效 |

> 约定：`tests/` 通过 `import <module>` 导入被测代码；`run_grader` 将 `solution_dir` 置于 `PYTHONPATH` 首位，因此 `tests/` 无需关心实现位于何处。

## 2. 如何使用 grader

### 编程调用

```python
from milestones.grader import run_grader

# 评学生提交
r = run_grader("milestones/m1_cli")
print(r.passed, r.summary)

# 评参考解（自检）
r = run_grader("milestones/m1_cli", solution="reference_solution")

# 评任意路径的实现
r = run_grader("milestones/m1_cli", solution_dir="/tmp/my_impl")
```

`run_grader` 内部调用 `pytest`（唯一评测引擎），返回 `GraderResult(passed, returncode, output, summary, tests_dir, solution_dir)`。

### 命令行

```bash
python -m milestones.grader milestones/m1_cli
python -m milestones.grader milestones/m1_cli --solution reference_solution
python -m milestones.grader milestones/m1_cli --solution-dir /tmp/my_impl
```

## 3. 如何新增一个里程碑

1. 建目录骨架：

   ```bash
   mkdir -p milestones/<new_name>/{student_solution,tests,reference_solution}
   ```

2. 在 `reference_solution/` 中实现教师参考解（已知正确）。
3. 在 `tests/` 中编写黑盒测试（`test_*.py`，pytest 发现规则）。测试只通过公开接口断言行为。
4. 将参考解复制到 `student_solution/` 作为初始模板，或留空让学生从零实现。
5. 自检（双反向验证）：

   ```bash
   bash milestones/grader_selfcheck.sh          # 全局三分支自检（示例里程碑）
   python -m milestones.grader milestones/<new_name> --solution reference_solution  # 应 PASS
   # 故意改错 reference_solution 后再跑，应 FAIL（证明测试能捉错）
   ```

6. 在 `book/_toc.yml` 与相关周章中加入里程碑导航与说明。

## 4. 双反向验证（为什么需要 `grader_selfcheck.sh`）

脚本 `milestones/grader_selfcheck.sh` 在 `/tmp` 构造一个极简示例里程碑（`add(a,b)`），用隔离 venv 执行三分支：

- **(a) 好解 → PASS** — 正确实现通过教师测试。
- **(b) 故意做错的解 → FAIL** — 带 off-by-one 的错解被教师测试判失败（`grader` 报告 FAIL）。
- **(c) 学生的测试套件 × 错解 → FAIL** — 学生的测试同样能捉住错解；若 (c) 通过，则测试集是“空心”的，判分恒绿。

> 仅当 (a) PASS 且 (b)(c) 均为 FAIL 时，自检通过。这正是 6.031 “用学生测试跑错解” 的核心保证。

脚本在 `/tmp/m2t-grader-venv` 创建隔离 venv（`python3 -m venv` + `pip install pytest`；若无网络则回退到本机 `python3 -m pytest` 并在日志中记录所用路径），结束时删除 venv（清理凭据打印于日志末尾）。

## 5. 常见问题

- **测试如何导入被测代码？** `run_grader` 将 `solution_dir` 注入 `PYTHONPATH`；测试中直接 `from mymodule import foo` 即可。
- **需要网络吗？** 评测本身不需要。`grader_selfcheck.sh` 的 venv 安装 `pytest` 需要一次网络；离线时自动回退到本机 pytest。
- **并发安全？** 评测无共享状态；`grader_selfcheck.sh` 的 venv 与 fixture 均在 `/tmp` 隔离，不触碰 `book/.venv`。
