---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

## 本章小结

- **类型是协作的书面合同**：Python 类型标注把“形状假设”显式化，`mypy`（尤其是严格模式）把“约定”变为“可检查的契约”；对 `m2t.audio` / `m2t.store` 等真实签名标注后，空值、联合类型与容器形状的错误可在提交前被捕获，而非在线上静默失败。
- **防御性编程让非法状态尽早失败**：在边界处校验输入、显式处理 `None` 分支、用 `Literal` 与 `dataclass` 让非法状态不可表示，比“深入调用栈后才抛错”更易定位与修复。
- **静态检查与格式化是协作噪声的收敛器**：`Ruff` 以单一配置一站式替代 `Flake8` / `Black` / `isort`，`pyproject.toml` 的 `select` 与 `line-length` 成为全仓单一事实源；`check --fix` 与 `format` 让风格与低级缺陷在提交前自动闭环，`git diff` 只承载业务变更。
- **测试金字塔与 AAA 让验证可分层、可回归**：单元测试覆盖纯函数与边界（如 `m2t.export`、`normalize_result`），集成测试验证 `store` 与 `export` 的协作，`E2E` 按需保留；AAA 模式让每个用例的准备、执行与断言清晰可溯，边界条件（空输入、单/多元素、非法格式、负时间戳）是真实用户输入而非额外负担。
- **Fixture 与 Mock 降低测试的成本与波动**：`fixture` 按 `function` / `module` / `session` 作用域复用准备逻辑与清理，`unittest.mock` 对 `ASR` / `LLM` / 文件系统等不稳定依赖提供替身；在“可观测行为”上断言，而非过度绑定实现细节。
- **覆盖率与门禁让信任可度量、可自动化**：行覆盖与分支覆盖是后视镜，揭示盲区但不保证正确；CI 中的 `ruff` / `mypy` / `pytest --cov --cov-fail-under` 构成质量门禁，本地与 CI 共用 `pyproject.toml`，阈值按“缺陷成本 × 变更频率”设定，避免为数字而测试。
- **贯穿启示**：类型、风格、测试与覆盖率四道工序共同服务于“可信交付”。MeetingToText 的 `m2t` 教学包（`audio` / `asr` / `store` / `export` / `llm`）在各节中被反复复用，正是为了展示“同一套护城河如何在不同章节的真实代码上持续生效”。

## 思考题

1. **标注的取舍**：`m2t.export` 的 `task` 参数既接受 `dict` 也接受对象，若用 `Any` 放行最省事，用 `TypedDict` + `Protocol` 精确约束则更安全。结合“标注维护成本 × 调用方多样性”，讨论何时应收窄、何时可适度放宽。
2. **严格模式的引入路径**：`mypy --strict` 对既有代码会产生大量告警。若你接手一个 2 万行的存量项目，会如何分阶段引入严格检查（按目录、按新文件、按 CI 增量门禁）而不过度阻塞迭代？
3. **Ruff 规则的团队共识**：`select = ["E", "F", "W", "I", "B", "UP", "SIM"]` 并非唯一答案。若团队对 `line-length` 与 `UP`（自动升级语法）存在分歧，你会如何通过数据（diff 噪声、CI 时长、成员反馈）而非偏好来达成一致？
4. **金字塔的变形**：MeetingToText 的音视频链路中，端到端测试成本高但信心强，单元测试快但离用户远。讨论在“无真实 ASR 模型”的教学环境中，如何用 `FakeModel` 与 `Mock` 把部分 E2E 信心下沉到集成层，以及这种下沉的边界在哪里。
5. **Mock 的度**：对 `LLMClient.generate` 的测试中，`assert_called_with` 能验证消息形状，但也会让测试与实现细节耦合。辨析“验证可观测输出”与“验证内部调用”的 trade-off，什么情况下应保留调用断言，什么情况下应移除。
6. **覆盖率的误用**：某次提交将行覆盖从 78% 提升到 92%，但新增用例仅让代码“被执行”而未断言关键分支（如 `TaskStore.get` 返回 `None` 的处理）。讨论如何通过“分支覆盖 + 关键路径清单”而非单一数字来评估测试充分性。
7. **门禁的演进**：假设 MeetingToText 从单人课程项目演进为多人协作的持续交付产品，CI 门禁从“本地可跑”扩展到“PR 必须通过 `ruff` / `mypy` / `pytest --cov-fail-under=80`”。这种变更会对开发者体验与合并节奏带来哪些影响？如何通过增量门禁与缓存来平衡安全与效率？

示例（本章贯通校验：用 `m2t` 串联“类型 → 风格 → 测试 → 覆盖率”最小闭环）：

```{code-cell} ipython3
import tempfile, pathlib

from m2t.store import TaskStore
from m2t.export import export
from m2t.asr import normalize_result

with tempfile.TemporaryDirectory() as td:
    db = pathlib.Path(td) / "summary.db"
    store = TaskStore(db)

    # 1) 类型与防御：创建任务（显式处理 None 分支）
    store.create("s1", "demo.wav", full_text="本章讲述类型、风格、测试与覆盖率")
    row = store.get("s1")
    assert row is not None
    print("stored:", row["filename"], row["status"])

    # 2) 测试思维：ASR 归一的边界（空结果与正常结果）
    assert normalize_result([]) == []
    segs = normalize_result([{"sentence_info": [{"text": row["full_text"], "start": 0, "end": 2000, "spk": 0}]}])
    assert len(segs) == 1
    assert segs[0]["speaker"] == "说话人1"
    print("normalize:", segs[0])

    # 3) 导出：复用 m2t.export 的纯函数能力（与存储解耦，便于单测）
    fake_task = {
        "id": row["id"],
        "filename": row["filename"],
        "result": {"duration": 2, "segments": segs},
        "minutes": "要点：护城河让重构有底气",
    }
    # txt / srt / md 三种格式均可回归
    assert "说话人1" in export(fake_task, "txt")
    assert "00:00:00,000" in export(fake_task, "srt")
    md = export(fake_task, "md")
    print(md.splitlines()[0])
    assert "demo.wav" in md
    print("闭环校验通过：store -> asr.normalize -> export 可独立测试与组合")
# 预期输出:
# stored: demo.wav pending
# normalize: {'speaker': '说话人1', 'text': '本章讲述类型、风格、测试与覆盖率', 'start': 0.0, 'end': 2.0}
# # 会议转录 — demo.wav
# 闭环校验通过：store -> asr.normalize -> export 可独立测试与组合
```
