---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

# 第8章 Vue3 核心机制与状态设计

> **本章学习目标**
> - 能够用 Proxy 与发布-订阅解释 Vue 3 响应式的本质，区分 `ref` / `reactive` / `computed` / `watch` 的适用边界，并说清组合式 API 生命周期的执行时机
> - 能够用 Props 向下、Emits 向上、Slots 内容分发的三条链路设计组件间通信，并判断何时应将逻辑抽为组合函数
> - 能够用 Vue Router 4 的历史模式、路由守卫与懒加载三件套设计前端路由，并解释守卫链的执行顺序与放行规则
> - 能够用 Pinia 的 Store / Action / Getter 三层模型组织跨组件状态，并说清前端状态与后端 `TaskStore` 的职责边界
> - 能够以后端视角读懂 Vue 3 组件、路由与状态的目录与契约，并与 FastAPI 接口完成前后端联调定位

> **为什么需要掌握本章**
> 第 7 章把前端的版图与工程基石讲透：你已知道前端为何要独立构建、Vue 3 为何被选中、Vite 如何让开发期变快。但“知道选型”不等于“能协作交付”——MeetingToText 的真实前端是“任务列表响应式过滤 + 组件拆分 + 路由切换 + 跨页面状态共享”，任何一环含糊，就会在联调时陷入“数据明明返回了为何视图不动”“父子组件到底谁改状态”“刷新后为何回到首页”的反复拉扯。本章以后端视角深入 Vue 3 的四块核心：响应式如何让数据变视图、组件如何划边界与传值、路由如何管页面、Pinia 如何管全局状态。掌握它们，你才能在前后端对话中既读懂前端目录，也能在接口契约与状态归属上做出不推诿的判断。

> **预计理论学时**：3学时

本章延续“先动机、后定义、再可运行示例”的节奏：每一节先讲清工程痛点，再给出最小可用定义，最后用一段可在本机复现的 `{code-cell}` 把概念固定下来。与第 1 至 7 章相同，所有示例均在书仓根目录的 `.venv` 环境中用标准库本地验证，无需启动真实的 ASR 模型、LLM 网络调用或前端 dev server。

章内结构如下：

- [8.1 响应式原理](8.1_reactivity_principles.md) —— Proxy vs defineProperty：依赖追踪如何工作；组合式 API 生命周期时机
- [8.2 组件化设计](8.2_component_design.md) —— Props / Emits / Slots 三条通信链路；组合函数复用边界
- [8.3 路由管理](8.3_routing_management.md) —— Vue Router 4 历史模式、路由守卫与懒加载
- [8.4 跨组件状态管理 Pinia](8.4_cross_component_state_pinia.md) —— Store / Action / Getters 模块化；与后端状态的边界

此外，本章所有可执行示例均可在书仓 `.venv` 环境中复现；涉及 MeetingToText 的片段复用 `m2t` 教学包，前端契约以通用内联示例呈现（如 `fetch('/mock.json')` 与 `v-for` 渲染的最小闭环），无需启动真实服务。

> **跨平台约定**：本章所有涉及路径与环境激活的命令均标注 Windows / macOS / Linux 差异，详见各小节对照表；正文跨章引用一律使用相对链接，如 [第1章 开发者的元技能](../../part1_software_engineering/chapter01_dev_meta_skills/index.md) 与 [第7章 前端概况](../chapter07_frontend_overview/index.md)。

文件 `book/part3_frontend_collaboration/chapter08_vue3_core/demo_index.py`（验证本章环境与 Vue 3 核心概念的最小协作闭环，本地可复现）：

```{code-cell} ipython3
# 文件 book/part3_frontend_collaboration/chapter08_vue3_core/demo_index.py
import sys, pathlib, json

import m2t
from m2t.store import TaskStore

print("m2t version:", m2t.__version__)
print("python:", sys.version.split()[0])
print("TaskStore:", TaskStore.__name__)

# 本章预告：用最小模型串联响应式→组件→路由→状态的协作直觉
# 1) 响应式：数据变，视图自动变（Proxy 心智）
class MiniRef:
    def __init__(self, v): self._v, self._subs = v, []
    @property
    def value(self): return self._v
    @value.setter
    def value(self, nv):
        self._v = nv
        for fn in self._subs: fn(nv)
    def watch(self, fn): self._subs.append(fn)

keyword = MiniRef("")
renders = []
keyword.watch(lambda v: renders.append(f"filter:{v or '*'}"))
keyword.value = "meeting"
keyword.value = ""
print("响应式:", renders)
assert renders == ["filter:meeting", "filter:*"]

# 2) 路由+状态：路由决定看哪页，状态决定页里有什么
routes = {"/tasks": "任务列表", "/tasks/1": "任务详情"}
store_tasks = [{"id": "1", "filename": "meeting.wav", "status": "done"}]
for path, label in routes.items():
    print(f"路由 {path} → {label} (数据 {len(store_tasks)} 条)")

# 3) 工程契约：内联 package.json 即前后端协作契约
pkg = {
    "name": "frontend-min",
    "type": "module",
    "dependencies": {"vue": "^3.4.0"},
    "devDependencies": {"vite": "^5.0.0", "vue-tsc": "^2.0.0"},
    "scripts": {"dev": "vite", "build": "vue-tsc -b && vite build", "preview": "vite preview"},
}
print("frontend deps:", list(pkg.get("dependencies", {}).keys()))
print("frontend scripts:", list(pkg.get("scripts", {}).keys()))
print("prefix:", pathlib.Path(sys.prefix).name)
# 预期输出:
# m2t version: 0.1.0
# python: 3.12.x
# TaskStore: TaskStore
# 响应式: ['filter:meeting', 'filter:*']
# 路由 /tasks → 任务列表 (数据 1 条)
# 路由 /tasks/1 → 任务详情 (数据 1 条)
# frontend deps: ['vue']
# frontend scripts: ['dev', 'build', 'preview']
# prefix: .venv 或系统前缀
```

```bash
# 本章所有 code-cell 均用 .venv 中的 Python 执行（macOS / Linux）
.venv/bin/python -c "import m2t, json, pathlib; print(m2t.__version__)"
# Windows 需用
.venv\Scripts\python.exe -c "import m2t, json, pathlib; print(m2t.__version__)"
```
