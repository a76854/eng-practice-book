---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

## 本章小结

- **响应式的本质是“代理 + 依赖追踪 + 自动通知”**：Vue 3 用 `Proxy` 代理整个对象，天然支持新增/删除与数组索引，摆脱了 `Object.defineProperty` 对已知属性的劫持局限；`ref` 管单值、 `reactive` 管对象、 `computed` 管派生缓存、 `watch`/`watchEffect` 管副作用，组合式 API 的 `onMounted`/`onUnmounted` 则把“何时拉数据、何时清理”与后端的请求/生命周期对照起来（见 [8.1 响应式原理](8.1_reactivity_principles.md)）。
- **组件化的本质是“按职责划边界，按契约做通信”**：Props 向下只读、Emits 向上事件、Slots 内容分发，三条链路覆盖全部父子通信；有 UI 的复用抽组件，无 UI 的逻辑复用抽组合函数（如 `useTasks`），两者结合即“组件包裹组合函数”（见 [8.2 组件化设计](8.2_component_design.md)）。
- **路由的本质是“URL → 组件”的映射 + 守卫链 + 懒加载分包**：`createWebHistory` 与 `createWebHashHistory` 在“干净 URL vs 零服务端配置”间 trade-off；`beforeEach`/`beforeEnter`/`beforeResolve`/`afterEach` 构成可类比后端中间件的守卫洋葱，`component: () => import(...)` 让 Vite/Rollup 按路由拆 chunk、首屏按需加载（见 [8.3 路由管理](8.3_routing_management.md)）。
- **Pinia 的本质是“单例 Store + State/Getter/Action 三层”**：State 是可变真相缓存，Getter 是带缓存的派生只读，Action 是唯一写入口（可异步）；按领域拆 `useTaskStore`/`useUserStore`，跨 store 通过显式调用协作；前端状态以后端为真相，刷新即以 `load()` 重拉为准，乐观更新失败则回滚（见 [8.4 跨组件状态管理Pinia](8.4_cross_component_state_pinia.md)）。
- **贯穿启示**：以后端视角看，Vue 3 的响应式是前端的“发布-订阅”、组件是“带契约的函数”、路由是“路径到处理器的映射”、Pinia 是“单例服务”——四者在 MeetingToText 的“列表过滤—组件拆分—路由切换—跨页共享”链路中闭环；读懂该闭环，才能在前后端联调中对“为何视图不动”“状态归谁管”“刷新后为何丢失”做出不推诿的定位。

## 思考题

1. **Proxy 的边界**：Proxy 能拦截新增属性，但对“新增后立即读取”的依赖收集时机有何要求？若一个组件在 `setup` 中新增 `state.newField` 后立即在 `watchEffect` 中读取，能否自动追踪？这对“先定义完整 State 形状”的工程规范有何启示？
2. **ref vs reactive 的选型**：在什么场景下优先用 `ref`、何时用 `reactive`？若 `reactive` 对象被解构（`const { tasks } = state`）会丢失响应性，你会如何用 `toRefs` 或“全用 ref”两种策略在团队中统一，并说明代价？
3. **组件边界的艺术**：MeetingToText 的任务卡片若同时需要“展示 + 编辑 + 播放”，你会拆为一个大组件还是“展示/编辑/播放”三个子组件 + 一个组合函数？请结合 Props 透传深度、复用度与测试粒度说明判断依据。
4. **守卫与鉴权的归属**：路由守卫 `beforeEach` 做前端鉴权拦截，后端亦有 JWT 中间件。两者如何分工才能既保证安全（以后端为准）又保证体验（前端提前拦截）？若前端守卫被绕过（如直接调接口），会发生什么、应如何防御？
5. **懒加载的粒度**：按路由懒加载能减小首屏，但过细的拆分会增加请求数。如何用 Vite/Rollup 的 `manualChunks` 在“首屏大小”与“请求数”间权衡？能否为 MeetingToText 的 `TaskList`/`TaskDetail`/`Upload` 设计一种“首屏 1 chunk + 详情按需”的分包策略？
6. **Pinia 与后端状态的一致性**：前端乐观更新“标记完成”后，若后端写入失败，前端应如何回滚并提示？对比“乐观更新 + 回滚”与“悲观等待后端成功再更新”，讨论两者的用户体验与实现复杂度 trade-off，并设计一种“可重试的乐观队列”。
7. **跨 Store 协作的依赖方向**：`useUploadStore` 的 `onUploaded` 调用 `useTaskStore().load()` 刷新列表，这种“Store 间直接调用”会引入循环依赖吗？何时应通过事件总线或父组件协调来解耦 Store 间的协作？

文件 `book/part3_frontend_collaboration/chapter08_vue3_core/demo_summary.py`（本章贯通校验：串联响应式→组件→路由→Pinia 的协作闭环，本地可复现，无网络）：

```{code-cell} ipython3
# 文件 book/part3_frontend_collaboration/chapter08_vue3_core/demo_summary.py
from typing import Callable
import re

# ---- 1) 响应式基建（同 8.1/8.4 的极简实现） ----
class Dep:
    def __init__(self): self.subs: list[Callable] = []
    def depend(self, fn):
        if fn not in self.subs: self.subs.append(fn)
    def notify(self):
        for fn in list(self.subs): fn()

_active: list[Callable] = []
def watchEffect(fn: Callable):
    def wrapped():
        _active.append(wrapped)
        try: fn()
        finally: _active.pop()
    wrapped()
    return wrapped

class Ref:
    def __init__(self, v): self._v, self._dep = v, Dep()
    @property
    def value(self):
        if _active: self._dep.depend(_active[-1])
        return self._v
    @value.setter
    def value(self, nv):
        if nv != self._v:
            self._v = nv
            self._dep.notify()

# ---- 2) 组件契约：Props 输入 + Emits 输出 + Slots 内容 ----
class TaskRow:
    def __init__(self, task: dict, slot_row=None):
        self.task = task
        self.slot_row = slot_row
    def render(self) -> str:
        if self.slot_row:
            return self.slot_row(task=self.task)
        return f"{self.task['filename']} — {self.task['status']}"

# ---- 3) 路由表：匹配 + 守卫 ----
class RouteRecord:
    def __init__(self, path, component, meta=None):
        self.path, self.component, self.meta = path, component, meta or {}
        pat = re.sub(r":(\w+)", r"(?P<\1>[^/]+)", path)
        self.regex = re.compile(f"^{pat}$")
    def match(self, url):
        m = self.regex.match(url)
        return m.groupdict() if m else None

routes = [
    RouteRecord("/tasks", "TaskList.vue"),
    RouteRecord("/tasks/:id", "TaskDetail.vue", {"requiresAuth": True}),
]

def navigate(url: str, authed=False):
    for r in routes:
        params = r.match(url)
        if params is not None:
            if r.meta.get("requiresAuth") and not authed:
                return "redirect:/login"
            return f"{r.component} params={params}"
    return "404"

# ---- 4) Pinia Store：State + Getter + Action ----
class MiniStore:
    def __init__(self):
        self.tasks, self.keyword = Ref([]), Ref("")
        self._cache, self._dirty, self._dep = None, True, Dep()
        def mark(): self._dirty = True; self._dep.notify()
        def track():
            _active.append(mark)
            try: _ = self.tasks.value; _ = self.keyword.value
            finally: _active.pop()
        watchEffect(track)
    @property
    def filtered(self):
        if _active: self._dep.depend(_active[-1])
        if self._dirty:
            kw = self.keyword.value.lower()
            self._cache = [t for t in self.tasks.value if kw in (t.get("name") or t.get("filename","")).lower()]
            self._dirty = False
        return self._cache
    def load(self, data): self.tasks.value = list(data)
    def set_keyword(self, v): self.keyword.value = v

# ---- 贯通校验：响应式→组件→路由→Pinia 闭环 ----
print("=== 本章贯通：MeetingToText 协作闭环 ===")

# 1) 响应式：keyword 变 → filtered 自动变
store = MiniStore()
store.load([
    {"id": "1", "filename": "meeting.wav", "status": "done"},
    {"id": "2", "filename": "interview.mp3", "status": "processing"},
])
store.set_keyword("meeting")
assert len(store.filtered) == 1
print("1) 响应式：keyword=meeting → filtered 1 条 ✓")

# 2) 组件：用 filtered 渲染 TaskRow（Props+Slots）
rows = [TaskRow(t, slot_row=lambda task: f"[{task['status']}] {task['filename']}").render() for t in store.filtered]
print("2) 组件：", rows[0])
assert "[done] meeting.wav" in rows[0]

# 3) 路由：切换到详情需鉴权
assert navigate("/tasks", authed=False) == "TaskList.vue params={}"
assert navigate("/tasks/42", authed=False) == "redirect:/login"
assert navigate("/tasks/42", authed=True) == "TaskDetail.vue params={'id': '42'}"
print("3) 路由：/tasks 放行，/tasks/42 未登录重定向，已登录放行 ✓")

# 4) Pinia 跨组件：另一组件读同一 store 的派生
store.set_keyword("")
assert len(store.filtered) == 2
print(f"4) Pinia：清空过滤后跨组件可见 {len(store.filtered)} 条 ✓")

# 5) 响应式联动：keyword 改 → 组件自动重渲染（模拟）
store.set_keyword("interview")
# filtered 已变，组件若监听则自动重渲染
assert [t["filename"] for t in store.filtered] == ["interview.mp3"]
print("5) 联动：keyword=interview → 组件自动得 interview.mp3 ✓")

print()
print("贯通校验通过：响应式→组件→路由→Pinia 在 MeetingToText 闭环中一致")
# 预期输出:
# === 本章贯通：MeetingToText 协作闭环 ===
# 1) 响应式：keyword=meeting → filtered 1 条 ✓
# 2) 组件： [done] meeting.wav
# 3) 路由：/tasks 放行，/tasks/42 未登录重定向，已登录放行 ✓
# 4) Pinia：清空过滤后跨组件可见 2 条 ✓
# 5) 联动：keyword=interview → 组件自动得 interview.mp3 ✓
# 贯通校验通过
```

> **跨平台提示**：本章贯通示例与操作系统无关；本地验证用 `pathlib.Path` 处理路径，虚拟环境激活为 `source .venv/bin/activate`（macOS / Linux）与 `.venv\Scripts\activate`（Windows）。

```bash
# 本章贯通校验（macOS / Linux）
.venv/bin/python -c "import pathlib; print(pathlib.Path('book/part3_frontend_collaboration/chapter08_vue3_core/demo_summary.py').exists())"
# Windows 需用
.venv\Scripts\python.exe -c "import pathlib; print(pathlib.Path('book/part3_frontend_collaboration/chapter08_vue3_core/demo_summary.py').exists())"
```
