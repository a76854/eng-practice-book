# 成绩等级评定系统

## 实验目标

通过构建一个成绩等级评定系统，你将：

1. **应用类型系统**：使用 `dataclass` 定义数据结构，使用 `pydantic` 做边界校验
2. **配置静态检查与类型检查**：在 `pyproject.toml` 中配置 Ruff 和 mypy，并修复所有告警
3. **编写测试**：为等级划分、统计分析、异常检测等逻辑编写单元测试
4. **建立 CI 流水线**：配置 GitHub Actions，让 Ruff → mypy → pytest 自动运行

> 这是一个**递进式实验**——四个实验任务依次构建，前一个任务的产出是后一个任务的基础。最终交付一个完整的、带测试的、CI 自动检查的 Python 项目。

---

## 背景故事

你是一名助教。本学期的公选课《工程实践》（课程代号 `6942083555982`）有 120 名学生，分别来自两个专业、四个自然班：`261041` 班、`261042` 班（软件工程）、`260851` 班、`260852` 班（人工智能），每班 30 人。期末成绩已汇总在一份 CSV 文件中。

你的任务是：

1. **加载数据**：读取 CSV，把每一行转成结构化对象
2. **校验数据**：检查学号、课程代号、成绩范围、必填字段，找出录入错误
3. **等级评定**：按分数段自动划分 A/B/C/D/F 等级，回填到 `等级` 列
4. **统计分析**：计算平均分、最高分、最低分、及格率、等级分布
5. **异常标记**：检出远低于平均分的学生，在 `备注` 列标注提醒复核

这个系统让教师一键完成以往“Excel 拉公式→筛选→人工核对”两天的工作量。

---

## 预备知识

**CSV 文件格式**（表头固定 7 列，`等级`/`备注` 初始留空由你的脚本回填）：

```
学号,姓名,班级,课程代号,成绩,等级,备注
26104101,张三,261041,6942083555982,85.5,,
26104102,李四,261041,6942083555982,92,,
26085115,王五,260851,6942083555982,67,,
26085203,赵六,260852,6942083555982,34,,
```

> 实际发放的 `labs/lab02/grades.csv` 共 120 行（4 班×30），成绩含小数，已留空 `等级`/`备注`。

**等级划分规则**：

| 等级 | 分数范围 | 说明 |
|------|----------|------|
| A | ≥ 90 | 优秀 |
| B | 80–89.99 | 良好 |
| C | 70–79.99 | 中等 |
| D | 60–69.99 | 及格 |
| F | < 60 | 不及格 |

**异常检测规则**：

检测"成绩低于平均值 - 2×标准差"的学生（离群值），在 `备注` 中写入 `异常：低于均值-2σ`。

---

# 任务一：定义数据结构

## 任务目标

用 `dataclass` 定义数据模型，用 `pydantic` 定义校验模型。

## 核心模型

**1. 学生记录模型（`dataclass`）**

在 `src/grade/models.py` 中定义：

```python
from dataclasses import dataclass
from typing import Literal

@dataclass
class StudentRecord:
    """单条学生成绩记录"""
    student_id: str      # 学号（8位）
    name: str            # 姓名
    class_name: str      # 班级（如 261041）
    course_id: str       # 课程代号（如 6942083555982）
    score: float         # 成绩（0-100，支持小数）
    grade: Literal["A", "B", "C", "D", "F"] | None = None   # 等级（初始 None，评定后回填）
    remark: str = ""     # 备注（异常标记，默认空）
```

**2. 校验模型（`pydantic`）**

在 `src/grade/schemas.py` 中定义，用于校验 CSV 的每一行数据：

```python
from pydantic import BaseModel, Field
from typing import Literal

class GradeRow(BaseModel):
    """CSV 行数据校验模型（用于边界校验）"""
    student_id: str = Field(pattern=r"^\d{8}$", description="8位数字学号")
    name: str = Field(min_length=1, max_length=20)
    class_name: str = Field(min_length=1)
    course_id: str = Field(pattern=r"^\d{13}$", description="13位数字课程代号")
    score: float = Field(ge=0, le=100)
    grade: Literal["A", "B", "C", "D", "F"] | None = Field(default=None)
    remark: str = Field(default="", max_length=200)
```

> 说明：`grade`/`remark` 在原始 CSV 中为空，`GradeRow` 需接受 `""`/`None`，并在 `validate_row` 中将空串归一为 `None`/`""` 后校验。

## 验收标准

| 验收项 | 说明 |
|--------|------|
| `StudentRecord` 包含全部 7 个字段 | 类型标注正确，`grade` 为 `Literal` 约束，含 `course_id`/`remark` |
| `GradeRow` pydantic 模型 | 学号8位、课程代号13位、成绩0-100支持小数、grade/remark可选 |
| 非法数据创建时抛 `ValidationError` | 测试用例验证 |

## 提交要求

```bash
git switch -c exp/01-data-models
git add src/grade/
git commit -m "feat(grade): define dataclass and pydantic models"
git push -u origin exp/01-data-models
```

---

# 任务二：实现数据加载与校验

## 任务目标

实现 CSV 读取与校验，把文件中的 `等级`/`备注` 留空视为待填充，加载为 `StudentRecord` 列表。

## 核心功能

在 `src/grade/loader.py` 中实现：

```python
import csv
from pathlib import Path
from typing import List
from src.grade.models import StudentRecord
from src.grade.schemas import GradeRow

def load_csv(file_path: Path) -> List[StudentRecord]:
    """
    从 CSV 文件加载成绩数据，校验每一行
    Args:
        file_path: CSV 文件路径
    Returns:
        List[StudentRecord]: 校验通过的学生记录列表（校验失败的行跳过并记录错误）
    Raises:
        FileNotFoundError: 文件不存在
        ValueError: 表头缺失/列名无法映射等致命格式错误
    """
    # TODO: 实现 CSV 读取与校验
    pass

def validate_row(row: dict) -> GradeRow:
    """
    校验单行数据
    Args:
        row: CSV 的 dict 行数据，键为列名
    Returns:
        GradeRow: 校验通过的模型实例
    Raises:
        ValidationError: 数据不合法
    """
    pass
```

**关键要求**：

1. CSV 列名不固定——需自动识别映射，至少支持：
2. 校验失败的行记录行号和原因并跳过，仅表头缺失/必要列无法映射时才抛 `ValueError`
3. 成绩为 `float`，CSV 中可能为 `"85"` 或 `"85.5"`，`GradeRow` 已支持小数，只需 `strip` 后交 `pydantic` 转换；`等级`/`备注` 为空时归一为 `None`/`""`
4. 课程代号全表应为 `6942083555982`，但校验模型仍需按 13 位数字校验，便于复用

```python
EXPECTED_COLUMNS = {
    "学号": ["学号", "ID", "编号", "student_id"],
    "姓名": ["姓名", "名字", "name"],
    "班级": ["班级", "班", "class", "class_name"],
    "课程代号": ["课程代号", "课程号", "course_id", "course"],
    "成绩": ["成绩", "分数", "score"],
    "等级": ["等级", "grade"],
    "备注": ["备注", "remark", "comment"],
}
```

## 静态检查要求

```bash
ruff check src/          # 零告警
mypy src/                # 零错误
ruff format src/         # 格式化通过
```

## 验收标准

| 验收项 | 说明 |
|--------|------|
| CSV 加载 | 正确读取 7 列 CSV，等级/备注为空时加载为 `None`/`""` |
| 列名自动识别 | 多种列名变体都能正确匹配 |
| 数据校验 | 学号8位、课程代号13位、成绩0-100、必填字段校验生效 |
| 错误处理 | 校验失败跳过并记录，致命错误才抛异常 |
| 类型标注 | 所有函数都有完整的类型标注 |
| Ruff/mypy | 零告警/零错误 |

## 提交要求

```bash
git switch -c exp/02-loader
git add src/grade/
git commit -m "feat(grade): implement CSV loader with validation"
git commit -m "style: fix ruff and mypy warnings"
git push -u origin exp/02-loader
```

---

# 任务三：实现等级评定、统计分析与异常标记

## 任务目标

实现等级自动评定、统计指标计算、异常检测并回填 `备注`。

## 核心功能

在 `src/grade/analyzer.py` 中实现（仅依赖 2 个数据模型，其余用内置类型）：

```python
from typing import List
from src.grade.models import StudentRecord

def calculate_stats(records: List[StudentRecord]) -> dict:
    """
    计算成绩统计指标
    Returns:
        dict: 含 average/max_score/min_score/pass_rate/distribution 等
        示例 {"average": 75.5, "max_score": 98, "min_score": 18.5,
              "pass_rate": 0.89, "distribution": {"A": 5, ...}}
    """
    pass

def assign_grade(score: float) -> str:
    """
    根据分数划分等级
    Returns:
        str: A/B/C/D/F
    """
    pass

def detect_anomalies(records: List[StudentRecord]) -> List[StudentRecord]:
    """
    检测异常学生并回填 remark
    规则：
      1) 成绩 < (平均值 - 2 * 标准差)
      2) 学号年份 > 26（未来年份，如 30xxxxxx，不可能出现）
    对命中者在 record.remark 写入原因（多原因用；拼接），并返回异常列表
    Returns:
        List[StudentRecord]: 异常学生列表（已写入 remark）
    """
    pass
```

**辅助函数**（可选，建议用 `statistics` 标准库）：

```python
import statistics

def calc_mean(scores: List[float]) -> float:
    return statistics.mean(scores)

def calc_stdev(scores: List[float]) -> float:
    # 样本数 <2 时 stdev 无定义，需兜底返回 0.0
    return statistics.stdev(scores) if len(scores) >= 2 else 0.0
```

**等级划分**：

| 等级 | 分数范围 |
|------|----------|
| A | ≥ 90 |
| B | 80–89.99 |
| C | 70–79.99 |
| D | 60–69.99 |
| F | < 60 |

**等级回填**：遍历 `records` 调用 `assign_grade` 写入 `record.grade`。

**异常标记**：`detect_anomalies` 需同时检查两类异常——成绩离群（同上）与学号年份异常（学号前两位 >26，如 `30994502` 视为未来年份不可能出现），命中者在 `record.remark` 写入 `异常：低于均值-2σ` 或 `异常：学号年份异常`，多原因用 `；` 拼接。

**示例**：

```python
# scores = [85.5, 92, 78, 34, 88, 90, 76], 另有学号 30994502
# mean ≈ 77.6, stdev ≈ 19.8, threshold = 38.0 → 34 成绩异常
# 30994502 → 学号异常，两者均写入 remark
```

## 验收标准

| 验收项 | 说明 |
|--------|------|
| 等级评定正确 | 所有边界值（90、80、70、60，含小数）测试通过，且能回填 `record.grade` |
| 统计计算正确 | 平均分、最高/最低分、及格率、分布准确（`calculate_stats` 返回 dict） |
| 异常标记正确 | 正确识别成绩离群 + 学号年份异常（>26）并写入 `remark`，返回 `List[StudentRecord]` |
| 类型标注完整 | 所有函数有类型标注 |

## 提交要求

```bash
git switch -c exp/03-analyzer
git add src/grade/
git commit -m "feat(grade): implement grading, statistics and anomaly detection"
git commit -m "style: fix ruff and mypy warnings"
git push -u origin exp/03-analyzer
```

---

# 任务四：编写测试（对应 2.3 测试与 CI）

## 任务目标

为所有核心功能编写完整的单元测试，覆盖正常路径、边界值和异常路径。

## 测试文件结构

```
tests/
├── __init__.py
├── conftest.py              # 共享 fixture
├── test_models.py           # dataclass 和 pydantic 模型测试
├── test_loader.py           # CSV 加载与校验测试
├── test_analyzer.py         # 统计、等级、异常检测测试
└── test_integration.py      # 端到端测试
```

## `conftest.py` 共享 fixture

```python
import pytest
from pathlib import Path
from src.grade.models import StudentRecord

COURSE_ID = "6942083555982"

@pytest.fixture
def sample_records() -> list[StudentRecord]:
    return [
        StudentRecord(student_id="26104101", name="张三", class_name="261041", course_id=COURSE_ID, score=85.5),
        StudentRecord(student_id="26104102", name="李四", class_name="261041", course_id=COURSE_ID, score=92),
        StudentRecord(student_id="26085101", name="王五", class_name="260851", course_id=COURSE_ID, score=67),
        StudentRecord(student_id="26085102", name="赵六", class_name="260851", course_id=COURSE_ID, score=34),
        StudentRecord(student_id="26104201", name="孙七", class_name="261042", course_id=COURSE_ID, score=90),
        StudentRecord(student_id="26085201", name="周八", class_name="260852", course_id=COURSE_ID, score=76),
    ]

@pytest.fixture
def sample_csv(tmp_path) -> Path:
    content = f"""学号,姓名,班级,课程代号,成绩,等级,备注
26104101,张三,261041,{COURSE_ID},85.5,,
26104102,李四,261041,{COURSE_ID},92,,
26085101,王五,260851,{COURSE_ID},67,,
"""
    p = tmp_path / "sample.csv"
    p.write_text(content, encoding="utf-8")
    return p

@pytest.fixture
def invalid_csv(tmp_path) -> Path:
    content = f"""学号,姓名,班级,课程代号,成绩,等级,备注
26104101,张三,261041,{COURSE_ID},85.5,,
abc,李四,261041,{COURSE_ID},92,,
26085101,王五,260851,{COURSE_ID},150,,
26085201,赵六,260852,999,78,, 
"""
    p = tmp_path / "invalid.csv"
    p.write_text(content, encoding="utf-8")
    return p
```

## 测试用例清单

**`test_models.py`**：

| 测试函数 | 测试场景 | 预期结果 |
|----------|----------|----------|
| `test_valid_student_record` | 合法创建 | 创建成功 |
| `test_grade_literal` | 等级只能 A/B/C/D/F/None | 非法值由 mypy 拦截，运行时 GradeRow 抛 ValidationError |
| `test_valid_grade_row` | 合法 GradeRow（含 course_id） | 创建成功 |
| `test_invalid_student_id` | 学号非8位 | ValidationError |
| `test_invalid_course_id` | 课程代号非13位 | ValidationError |
| `test_invalid_score` | 成绩<0或>100 | ValidationError |

**`test_loader.py`**：

| 测试函数 | 测试场景 | 预期结果 |
|----------|----------|----------|
| `test_load_valid_csv` | 加载合法 7列 CSV | 返回正确记录数，grade为None |
| `test_load_file_not_found` | 文件不存在 | FileNotFoundError |
| `test_invalid_csv` | 含非法学号/成绩/课程号 | 跳过非法行 |
| `test_column_mapping` | 列名变体 | 自动识别 |
| `test_empty_csv` | 空文件 | 返回空列表 |

**`test_analyzer.py`**：

| 测试函数 | 测试场景 | 预期结果 |
|----------|----------|----------|
| `test_calculate_stats` | 统计指标 | 均分、最高/最低分、及格率正确 |
| `test_assign_grade`（parametrize） | 含 90/89.99/80/60 边界 | 正确 |
| `test_distribution` | 等级分布 | 各等级人数正确 |
| `test_detect_anomalies` | 异常检测 | 正确识别成绩离群 + 学号年份异常（>26）并写入 remark |
| `test_detect_future_id` | 学号年份异常（如 30994502） | 标记 `异常：学号年份异常` |
| `test_no_anomalies` | 无异常 | 空列表 |
| `test_single_student` | 1人 | 不崩溃 |

**`test_integration.py`**：

| 测试函数 | 测试场景 | 预期结果 |
|----------|----------|----------|
| `test_full_pipeline` | CSV→等级回填→统计→异常标记 | 等级/备注/统计全正确 |

## 覆盖率要求

```bash
pytest tests/ --cov=src/grade --cov-report=term --cov-report=html
```

- **总覆盖率 ≥ 85%**
- **`analyzer.py` 覆盖率 ≥ 85%**

## 验收标准

| 验收项 | 说明 |
|--------|------|
| 所有测试通过 | `pytest tests/` 绿色 |
| 覆盖率达标 | ≥ 85% |
| 使用 `parametrize` | `test_assign_grade` 至少6组（含小数） |
| 使用 `fixture` | `sample_records`、`sample_csv`、`invalid_csv` |
| 使用 `tmp_path` | 测试 CSV 读写 |

## 提交要求

```bash
git switch -c exp/04-testing
git add tests/ src/grade/
git commit -m "test: add unit tests for all modules"
git commit -m "test: achieve 85% coverage"
git push -u origin exp/04-testing
```

---

# 任务五：建立 CI 流水线

## 任务目标

配置 GitHub Actions 流水线，让每次 push 和 PR 自动运行 Ruff、mypy、pytest。

## CI 配置文件

创建 `.github/workflows/ci.yml`：

```yaml
name: CI

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install uv
        run: pip install uv

      - name: Install dependencies
        run: uv sync --dev

      - name: Ruff check
        run: uv run ruff check src/

      - name: Ruff format
        run: uv run ruff format --check src/

      - name: mypy
        run: uv run mypy src/

      - name: Test with coverage
        run: uv run pytest tests/ --cov=src/grade --cov-report=term --cov-report=xml

      - name: Upload coverage to Codecov (optional)
        uses: codecov/codecov-action@v4
        with:
          file: ./coverage.xml
          fail_ci_if_error: false
```

## 验收标准

| 验收项 | 说明 |
|--------|------|
| CI 工作流已创建 | `.github/workflows/ci.yml` 存在 |
| CI 通过 | 在 PR 中看到绿色 |
| 所有阶段执行 | Ruff → mypy → pytest 依次运行 |
| 覆盖率报告上传 | Codecov 或 artifacts 可查看 |

## 提交要求

```bash
git switch -c exp/05-ci
git add .github/workflows/
git commit -m "ci: add GitHub Actions workflow"
git push -u origin exp/05-ci
```

---

# 综合验收标准

| 验收项 | 说明 |
|--------|------|
| 项目结构 | `src/grade/` + `tests/`，`pyproject.toml` 配置完整 |
| 类型系统 | `dataclass` + `pydantic` 合理使用（含 course_id） |
| 数据加载 | 7列 CSV 读取成功，等级/备注留空正确处理，列名自动识别 |
| 等级评定 | 按规则划分 A/B/C/D/F 并回填 |
| 统计分析 | 平均分、最高/最低分、及格率、分布正确 |
| 异常标记 | 低于 mean-2*stdev 的学生在备注中正确标记 |
| 静态检查 | Ruff 零告警，mypy 零错误 |
| 测试 | 全部通过，覆盖率 ≥ 85% |
| CI | GitHub Actions 绿色 |
| 提交历史 | 五个任务分别有独立 PR，提交信息符合规范 |

---

# 实验报告要求

将五个任务的 PR 链接汇总，提交一份实验报告，包含：

1. **项目概述**：系统实现了哪些功能
2. **五份 PR 链接**：每个任务一个 PR，附带简要说明
3. **工具链总结**：
   - `pydantic` 帮你拦截了哪些非法数据？
   - `mypy` 发现了哪些类型错误？
   - `pytest` 的测试覆盖率是多少？哪部分最难测试？
4. **遇到的问题及解决过程**（至少 3 个）
5. **实验收获与反思**

---

# 评分参考

| 部分 | 分值 | 说明 |
|------|------|------|
| 任务一：数据结构 | 15% | dataclass + pydantic 模型完整（含 course_id/等级/备注） |
| 任务二：数据加载与校验 | 20% | 7列 CSV 读取、列名识别、校验 |
| 任务三：等级与分析 | 20% | 等级回填、统计、异常标记全部正确 |
| 任务四：测试 | 20% | 测试覆盖 ≥ 85%，合理使用 fixture/parametrize |
| 任务五：CI | 10% | 流水线配置正确，全部阶段绿色 |
| 实验报告 | 15% | 内容完整、反思深入、PR 链接齐全 |
