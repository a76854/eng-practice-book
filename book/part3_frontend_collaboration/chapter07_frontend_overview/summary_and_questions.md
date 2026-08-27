---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

## 本章小结

- **前端在架构中的边界是“谁来拼 HTML”与“URL 如何分层”**：后端模板在服务端直出 HTML，适合内容型与 SEO 强依赖场景；前后端分离让后端聚焦 JSON 接口、前端聚焦交互与状态，接口通过 `/api` 前缀与 OpenAPI 契约解耦，MeetingToText 选择后者以支撑“上传—转写—列表—纪要”的多端复用链路（见 [7.1 前端在架构中的角色](7.1_frontend_role_in_architecture.md)）。
- **框架选型是约束的 trade-off，而非能力的排名**：React 以显式与可预测见长（`UI = f(state)`、单向、JSX），Vue 以渐进与直觉见长（模板、Proxy 自动追踪、SFC），Angular 以企业级完备见长（DI、RxJS、官方全家桶）；五维度 checklist（团队熟悉度、项目约束、规范诉求、生态宽度、长期维护）比“谁更流行”更可靠（见 [7.2 框架三驾马车](7.2_framework_troika.md)）。
- **Vue 3 + Vite 的选型可解释为“贴合本课程约束”**：组合式 API 把同一关注点的状态与逻辑收拢并可函数级复用，Proxy 代理整个对象解决了新增属性与数组的响应式盲区，Vite 开发期按需 ESM + 依赖预构建（esbuild）让“改一行、瞬时可见”，生产期再由 Rollup 做 tree-shaking 与分包（见 [7.3 为何选择 Vue 3 + Vite](7.3_why_vue3_vite.md)）。
- **前端工程化由“运行时 + 包管理 + 模块系统”三件套支撑**：Node.js 是前端工具的宿主运行时（Vite、`vue-tsc` 均跑在 Node 上），npm/pnpm 通过 lockfile 保证可复现、pnpm 以内容寻址 store + 符号链接实现省空间与严格依赖，ES Module 的静态 `import`/`export` 让工具可不执行代码即做依赖图与摇树——三者共同构成前端的“可复现、可审计、可按需”基座，与后端的 Python + `pyproject.toml` + `import` 形成镜像（见 [7.4 前端工程化基石](7.4_frontend_engineering_foundation.md)）。
- **贯穿启示**：以后端视角读懂前端目录（`src/`/`components`/`router`）、契约（`GET /api/tasks` 与三态渲染）与产物（`dist/` 静态资源），是前后端有效协作的前提；后续 [第8章 Vue 3 核心机制与状态设计](../chapter08_vue3_core/index.md) 将在该基座上展开响应式、组件化、路由与 Pinia 的完整链路。

## 思考题

1. **渲染边界再辨析**：若 MeetingToText 新增一个面向搜索引擎的营销落地页，你会为该页选择“后端模板直出”还是“前后端分离 + SSR/预渲染”？请结合首屏、SEO 与部署复杂度说明判断依据与代价。
2. **选型可复盘性**：假设团队从 3 人扩至 15 人，且需同时交付 Web 与小程序，你会如何重新评估 [7.2 的五维度 checklist](7.2_framework_troika.md) 的权重？哪一维度的变化最可能推翻“Vue 3 + Vite”的结论？
3. **组合式 vs 选项式**：在什么规模下，组合式 API 的“按关注点收拢”会从优势变为负担（如过度抽象）？能否为 MeetingToText 的“任务轮询”逻辑设计一个“何时抽为 `usePolling`、何时留在组件内”的判断标准？
4. **响应式的心智代价**：Proxy 的“改数据即改视图”降低了样板，但也让“何时触发更新”变得隐式。对比 React 的显式 `setState`，讨论隐式响应式在调试与可预测性上的利弊，并提出一种“让隐式变得可观测”的工程实践（如日志、devtools 或单向约束）。
5. **Vite 的边界**：Vite 开发期按需的优势在何种场景下会削弱（如超大依赖、频繁跨包修改）？若你的后台系统需在无 Node 的内网环境交付 `dist/`，你会如何设计“开发期用 Vite、交付期仅交付静态资源”的可审计流水线？
6. **包管理的诚实性**：pnpm 的严格依赖会让幽灵依赖直接失败，而 npm 的扁平可能让其“侥幸可跑”。讨论“严格失败”与“宽松兼容”对团队协作的长期影响：短期便利与长期可维护性应如何权衡？
7. **ESM 静态性的启发**：ESM 的静态 `import` 让 tree-shaking 成为可能，Python 的 `import` 则更动态。能否为 MeetingToText 的 Python 工具链设计一种“静态可分析的插件注册”机制，以获得类似的“未使用即剔除”能力？这种机制会带来哪些约束？

文件 `book/part3_frontend_collaboration/chapter07_frontend_overview/demo_summary.py`（本章贯通校验：以后端视角串联“接口契约 → 响应式过滤 → 工程契约”，本地可复现，无网络）：

```{code-cell} ipython3
import json, pathlib, re
from dataclasses import dataclass, asdict

# ---- 1) 接口契约：后端返回的任务 JSON，前端据此做三态渲染（对接 7.1） ----
@dataclass
class Task:
    id: str
    filename: str
    status: str

tasks = [Task("1", "meeting.wav", "done"), Task("2", "interview.mp3", "processing"), Task("3", "demo.wav", "pending")]
payload = {"tasks": [asdict(t) for t in tasks]}
json_text = json.dumps(payload, ensure_ascii=False)
data = json.loads(json_text)
assert len(data["tasks"]) == 3
print("契约校验通过：后端 JSON 可被前端解析，任务数", len(data["tasks"]))

# ---- 2) 响应式过滤：Proxy 心智的 Python 类比（对接 7.2/7.3） ----
class Reactive:
    def __init__(self, d: dict):
        object.__setattr__(self, "_d", dict(d))
        object.__setattr__(self, "_subs", {})
    def effect(self, key, fn):
        self._subs.setdefault(key, []).append(fn)
    def __getattr__(self, k):
        return self._d[k]
    def __setattr__(self, k, v):
        if k in ("_d", "_subs"):
            object.__setattr__(self, k, v)
        else:
            self._d[k] = v
            for fn in self._subs.get(k, []):
                fn()

state = Reactive({"keyword": "", "tasks": list(tasks)})
views: list[list[str]] = []

def compute():
    kw = state.keyword.lower()
    views.append([t.filename for t in state.tasks if kw in t.filename.lower()])

compute()
state.effect("keyword", compute)
state.keyword = "meeting"
print("响应式过滤:", views[-1])
assert views[-1] == ["meeting.wav"]
state.keyword = ""
print("清空过滤:", views[-1])
assert len(views[-1]) == 3
print("响应式校验通过：改数据即改视图")

# ---- 3) 工程契约：package.json 的脚本与 ESM 静态可分析（对接 7.4） ----
pkg = {
    "name": "frontend-min",
    "type": "module",
    "dependencies": {"vue": "^3.5.13"},
    "devDependencies": {"vite": "^6.0.0", "vue-tsc": "^2.0.0"},
    "scripts": {"dev": "vite", "build": "vue-tsc --noEmit && vite build", "preview": "vite preview"},
}
assert pkg["type"] == "module"
assert "dev" in pkg["scripts"] and "build" in pkg["scripts"]
print("工程契约：type=module 且 dev/build 存在")

esm_sample = "import { ref } from 'vue'\nimport { formatDuration } from './utils/format.js'\n"
imps = re.findall(r"from\s+['\"]([^'\"]+)['\"]", esm_sample)
print("ESM 静态导入:", imps)
assert "vue" in imps
print("ESM 静态分析通过：无需执行即可得依赖图")
print()

# ---- 4) 环境与协作：pathlib 统一路径，前后端通过契约协作 ----
dist = pathlib.Path("frontend/dist/index.html")
print("产物路径 (POSIX):", dist.as_posix())
print("协作闭环：后端 JSON → 前端响应式过滤 → ESM 产物可部署为静态资源")
print("本章贯通校验通过")
# 预期输出:
# 契约校验通过：后端 JSON 可被前端解析，任务数 3
# 响应式过滤: ['meeting.wav']
# 清空过滤: ['meeting.wav', 'interview.mp3', 'demo.wav']
# 响应式校验通过：改数据即改视图
# 工程契约：type=module 且 dev/build 存在
# ESM 静态导入: ['vue', './utils/format.js']
# ESM 静态分析通过：无需执行即可得依赖图
# 产物路径 (POSIX): frontend/dist/index.html
# 协作闭环：后端 JSON → 前端响应式过滤 → ESM 产物可部署为静态资源
# 本章贯通校验通过
```

```bash
# 本章贯通校验
.venv/bin/python -c "import m2t, json; pkg={'type': 'module'}; print(m2t.__version__); print(pkg['type'])"
```
