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

# 周12 前端基础：Vue3

> 为什么这一章要放在后端与持久化之后？前几周你已能启动 FastAPI 服务、持久化任务、排队转写——但这些能力还锁在「命令行与 `curl`」里，真实的 MeetingToText 是「浏览器里可点的任务列表页」。Vue 3（渐进式前端框架）是把「`GET /api/tasks` 的 JSON」变成「可交互页面」的桥梁：用组件（component）拆页面、用响应式（reactivity）让数据驱动视图、用 `v-model` 做输入双向绑定、用 `fetch` 消费后端 API。本章以 `frontend/src/views/TasksListPage.vue` 与 `frontend/src/api/client.ts` 为锚，带你从零写出一个消费 API 的任务列表页，并在 `book/samples/vue-min/` 留下一个最小可运行样例。

## 学习目标

完成本章后，你将能够：

1. 能解释 Vue 3 单文件组件（Single-File Component，SFC）的三段式结构（`<script setup>` / `<template>` / `<style>`），并编写一个含 `ref` 响应式状态的最小组件。
2. 能区分 `ref` 与 `reactive` 的使用场景，解释 `ref` 需 `.value` 而模板中自动解包的原因，并预测修改 `.value` 后视图的更新行为。
3. 能用 `v-model` 实现输入框与状态的双向绑定（two-way binding），并对比「单向 `:value` + `@input`」与 `v-model` 的等价性。
4. 能用 `fetch`（或封装的 `request`）在 `onMounted` 中请求 `GET /api/tasks`，处理 `loading / error / empty / list` 四态，并用 `v-for` 渲染 `<ul><li>` 列表。

## 先修要求

- 完成 [周7 HTTP 与 REST API](week07_HTTP与REST_API.md)（会读 `GET /api/tasks` 的请求/响应与状态码，理解 `frontend/src/api/client.ts` 的 `request` 封装）。
- 完成 [周1 环境与项目骨架](week01_环境与项目骨架.md) 的 Node/npm 部分（会 `cd book/samples/vue-min && npm install && npm run build`）。
- 会读 MeetingToText `frontend/src/views/TasksListPage.vue` 与 `frontend/src/api/client.ts`（只读参考，不需启动后端）。
- Python 基础与 `pytest`（本章习题为 hermetic 纯函数，用 Python 映射 Vue 概念）。

## 正文

### 12.1 组件与单文件组件：页面的最小积木

Vue 的核心思想是「组件化（componentization）」：把页面拆成可复用的组件，每个组件是一个 `.vue` 文件（SFC），包含三块：

```html
<script setup lang="ts">
import { ref } from 'vue'
const count = ref(0)
function inc() { count.value++ }
</script>

<template>
  <button @click="inc">点击 {{ count }}</button>
</template>

<style scoped>
button { padding: 6px 12px; }
</style>
```

- `<script setup>`：组合式 API（Composition API）入口，`import` 的变量与函数直接在模板中可用，无需 `export default`。
- `<template>`：声明式视图，`{{ count }}` 插值、`@click` 绑定事件、`v-for` 循环、`v-if` 条件。
- `<style scoped>`：仅作用于本组件的样式，避免全局污染。

MeetingToText 的 `TasksListPage.vue` 即一个典型 SFC：`<script setup>` 中定义 `tasks = ref([]) / loading / error` 并导入 `api.listTasks()`，`<template>` 中用 `v-for="t in tasks"` 渲染卡片、`v-if="error"` 显示错误。最小样例 `book/samples/vue-min/src/App.vue` 把该模式精简为 `fetch` 一个 mock 列表并渲染 `<ul>`。

### 12.2 响应式：`ref` 与 `reactive`

响应式（reactivity）指「数据变、视图自动变」。Vue 3 用 `Proxy` 实现：

```js
import { ref, reactive } from 'vue'

// ref：包裹任意值（含原始类型），读写经 .value
const count = ref(0)
count.value = 1  // 触发视图更新
// 模板中自动解包：{{ count }} 无需 .value

// reactive：包裹对象/数组，读写直接属性
const state = reactive({ tasks: [], loading: true })
state.loading = false
state.tasks.push({ id: '1', status: 'done' })
```

规则：

- 原始类型（`string/number/boolean`）必须用 `ref`。
- 对象/数组可用 `reactive`，但解构会丢失响应性；`ref` 包对象亦可，内部仍为 `reactive`。
- `ref` 在 `<script>` 中需 `.value`，在 `<template>` 中自动解包是编译器语法糖。

```{code-cell} ipython3
# 本章 JS 无法在 ipython3 直接执行，故用 Python 映射演示“响应式概念”
# Python 版 ref：一个带 .value 的盒子，set 时记录变更（类比 Vue 的 trigger）

class Ref:
    def __init__(self, value):
        self._value = value
        self.changes = []
    @property
    def value(self):
        return self._value
    @value.setter
    def value(self, new):
        self._value = new
        self.changes.append(new)

count = Ref(0)
count.value = 1
count.value = 2
print("count.value:", count.value)
print("changes:", count.changes)
assert count.value == 2
assert count.changes == [1, 2]
print("—— ref 语义：.value 读写，变更可追踪 ——")
```

`TasksListPage.vue` 的 `tasks = ref<TaskListItem[]>([])` 即此模式：`tasks.value = res.tasks` 触发 `v-for` 重新渲染。

### 12.3 `v-model`：双向绑定的语法糖

`v-model` 是「单向绑定 + 事件监听」的语法糖（syntactic sugar）：

```html
<!-- 这两行等价 -->
<input v-model="keyword" placeholder="搜索任务" />
<input :value="keyword" @input="keyword = ($event.target as HTMLInputElement).value" />
```

对组件亦然：`v-model` 默认绑定 `modelValue` prop 并监听 `update:modelValue` 事件。`TasksListPage.vue` 的重命名对话框中 `onUpdate:value` 即手写的 `v-model` 等价：

```js
h(NInput, {
  defaultValue: t.name || '',
  'onUpdate:value': (v) => { inputValue = v }
})
```

若改用 `<NInput v-model:value="inputValue" />` 则编译器自动生成该监听。

### 12.4 用 `fetch` 消费 API：`api/client.ts` 的封装

浏览器原生 `fetch` 是「发 HTTP 请求、收 `Response`」的 Promise API。MeetingToText 的 `api/client.ts` 在其上包了一层 `request`：

```js
const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api'

async function request(url, options) {
  const res = await fetch(API_BASE + url, {
    headers: { 'Content-Type': 'application/json', ...options?.headers },
    ...options,
  })
  if (!res.ok) {
    const data = await res.json().catch(() => ({}))
    throw new Error(data.detail || res.statusText)
  }
  return res.json()
}

export const api = {
  listTasks: () => request('/tasks'),
  getTask: (id) => request(`/task/${id}`),
}
```

视图侧在 `onMounted` 中调用：

```js
import { ref, onMounted } from 'vue'
import { api } from '../api/client'

const tasks = ref([])
const loading = ref(true)
const error = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await api.listTasks()
    tasks.value = res.tasks
  } catch (e) {
    error.value = e.message || '加载失败'
  } finally {
    loading.value = false
  }
}

onMounted(load)
```

模板中四态分支：

```html
<template>
  <div>
    <button @click="load" :disabled="loading">刷新</button>
    <p v-if="error" class="error">{{ error }}</p>
    <p v-else-if="loading">加载中...</p>
    <p v-else-if="!tasks.length">暂无任务</p>
    <ul v-else>
      <li v-for="t in tasks" :key="t.id">
        {{ t.name || t.filename }} — {{ t.status }}
      </li>
    </ul>
  </div>
</template>
```

关键点：`fetch` 返回 `Promise<Response>`，需 `await res.json()` 二次等待；`!res.ok` 时抛错由 `catch` 收敛到 `error` 状态；`v-for` 必须带 `:key` 以便 Vue 高效 diff。

### 12.5 应用：消费 API 的任务列表页

把 12.1–12.4 拼成完整页（精简版 `TasksListPage.vue`，对照 `book/samples/vue-min/src/App.vue`）：

```html
<script setup lang="ts">
import { ref, onMounted } from 'vue'

interface Task { id: string; filename: string; name?: string; status: string }

const tasks = ref<Task[]>([])
const loading = ref(true)
const error = ref('')
const keyword = ref('')

async function load() {
  loading.value = true
  error.value = ''
  try {
    const res = await fetch('/api/tasks').then(r => {
      if (!r.ok) throw new Error(r.statusText)
      return r.json()
    })
    tasks.value = res.tasks
  } catch (e: any) {
    error.value = e.message || '加载失败'
  } finally {
    loading.value = false
  }
}
onMounted(load)
</script>

<template>
  <div>
    <h1>历史任务</h1>
    <input v-model="keyword" placeholder="搜索任务" />
    <button @click="load" :disabled="loading">刷新</button>
    <p v-if="error">{{ error }}</p>
    <p v-else-if="loading">加载中...</p>
    <p v-else-if="!tasks.length">暂无任务</p>
    <ul v-else>
      <li v-for="t in tasks.filter(x => (x.name || x.filename).includes(keyword))" :key="t.id">
        {{ t.name || t.filename }} — {{ t.status }}
      </li>
    </ul>
  </div>
</template>
```

对照真实 `TasksListPage.vue` 的增强：用 `naive-ui` 的 `NCard/NTag/NSpin/NEmpty/NAlert` 替代原生 `<ul>/<p>`，用 `api.listTasks()` 替代裸 `fetch`，用 `formatDuration/formatDateTime` 格式化字段，用 `router.push` 跳转详情——但数据流（`ref` → `fetch` → `tasks.value` → `v-for`）完全一致。`book/samples/vue-min` 进一步把后端替换为 `fetch('/mock.json')` 的静态 mock，使 `npm run build` 无需后端即可产出 `dist/index.html`。

### 12.6 构建与部署：Vite 的作用

Vite 是 Vue 官方的构建工具（build tool）：开发时按需 ESM 加载实现秒级热更新（HMR），生产时用 Rollup 打包为 `dist/` 静态资源。

```bash
cd book/samples/vue-min
npm install          # 依据 package.json + package-lock.json 安装 vue/vite/@vitejs/plugin-vue/typescript
npm run build        # vue-tsc --noEmit 类型检查 + vite build 打包，产出 dist/index.html
npm run dev          # 可选：vite 启动 5173 开发服务器
```

`vite.config.ts` 仅需 `plugins: [vue()]` 即可支持 SFC；`tsconfig.json` 设 `strict: true` 与 `moduleResolution: bundler` 以兼容 Vite 的 ESM 解析。

### 改动并预测

以下实验均可在 `book/samples/vue-min` 或本章 `{code-cell}` 中复现。按「改什么 → 预测 → 解释」三段式。

#### 改动并预测 实验 1：把 `ref(0)` 改为 `reactive({ count: 0 })` 并去掉 `.value` → 预测模板与脚本行为

- **改什么**：把 `<script setup>` 中的 `const count = ref(0)` 与 `count.value++` 改为 `const state = reactive({ count: 0 })` 与 `state.count++`，模板中 `{{ count }}` 改为 `{{ state.count }}`。
- **预测**：视图仍能正常自增；但若在脚本中解构 `const { count } = state` 后再 `count++`，视图不再更新。
- **解释**：`ref` 与 `reactive` 均为响应式源，`state.count` 的读写仍经 `Proxy` 劫持；解构会剥离 `Proxy`，得到普通变量，故丢失追踪。`ref` 需 `.value` 正是为“包裹原始类型”提供统一劫持入口，模板自动解包掩盖了这一差异。

#### 改动并预测 实验 2：把 `v-model="keyword"` 改为 `:value="keyword"`（删掉 `@input`）→ 预测输入行为

- **改什么**：把 `<input v-model="keyword" />` 改为 `<input :value="keyword" />`（仅单向绑定，不监听输入）。
- **预测**：输入框初始显示 `keyword` 的值，但敲键盘后 `keyword` 不再变化，`{{ keyword }}` 与过滤列表 `tasks.filter(...)` 保持旧值，搜索失效。
- **解释**：`v-model` 等价于 `:value` + `@input` 双向；删掉事件监听即退化为单向，视图到数据的通路断开。`TasksListPage.vue` 的 `onUpdate:value` 正是手写版的 `@input` 通路。

#### 改动并预测 实验 3：把 `fetch('/api/tasks')` 改为 `fetch('/api/tasks?status=done')` 并去掉前端 `filter` → 预测数据与职责

- **改什么**：把 `load()` 中的 `fetch('/api/tasks')` 改为 `fetch('/api/tasks?status=done')`，并把模板中的 `tasks.filter(...)` 搜索过滤改为直接 `v-for="t in tasks"`（假设后端支持 `status` 查询参数）。
- **预测**：`tasks` 初始仅含 `done` 任务，前端不再做状态过滤；若后端未实现 `?status` 参数则返回全量或 400，需回退或加 `if (!res.ok)` 分支。
- **解释**：`fetch` 的 URL 构造决定「让后端过滤还是前端过滤」；服务端过滤减少传输与前端计算，但依赖 API 契约。`api/client.ts` 的 `request(API_BASE + url)` 拼接即暴露该契约点，习题的 `build_api_url` 覆盖此逻辑。

#### 改动并预测 实验 4：把 `onMounted(load)` 改为按钮点击才 `load` 且删掉 `loading` 状态 → 预测首屏与并发点击

- **改什么**：删掉 `onMounted(load)`，仅保留 `<button @click="load">刷新</button>`，并把 `loading` 相关 `ref` 与 `v-if="loading"` 删掉。
- **预测**：首屏 `tasks` 恒为空（`[]`），需用户手动点“刷新”才出现列表；快速连点“刷新”会并发多个 `fetch`，后完成的响应可能覆盖先完成的，导致列表闪烁或与预期不一致。
- **解释**：`onMounted` 保证首屏自动拉取；`loading` 既是 UI 反馈（`加载中...` / 禁用按钮）也是并发 guard（`:disabled="loading"` 防止重复请求）。`TasksListPage.vue` 的 `NSpin :show="loading"` 与 `NButton :loading` 均服务于此四态机（`loading/error/empty/list`）。

## 习题

> 参考答案与测试在 `answers/week12/`，运行 `.venv/bin/pytest answers/week12/ -q` 验证。题目均为 hermetic 纯函数，不依赖网络/浏览器/Vue 运行时；与 `frontend/src/views/TasksListPage.vue` 与 `frontend/src/api/client.ts` 的逻辑一一对应，改签名即测试失败。

1. **URL 构造**：实现 `build_api_url(base: str, path: str) -> str`，拼接 `API_BASE` 与路径（处理尾斜杠、空 base 回退为 `/api` 的边界），要求 `build_api_url("/api", "/tasks") == "/api/tasks"` 且 `build_api_url("/api/", "/tasks") == "/api/tasks"`。
2. **状态文案映射**：实现 `task_status_label(status: str) -> str`，将 `pending/processing/done/error` 映射为 `等待中/转写中/已完成/失败`，未知返回原值（与 `TasksListPage.vue` 的 `statusLabel` 一致）。
3. **状态类型映射**：实现 `task_status_type(status: str) -> str`，将 `done→success, processing→info, pending→warning, error→error`，未知返回 `default`（与 `statusType` 一致）。
4. **图标选择**：实现 `task_icon(has_minutes: bool, has_transcript: bool) -> str`，`has_minutes` 优先返回 `📋`，否则 `has_transcript` 返回 `📝`，否则 `🎙️`（与 `taskIcon` 一致）。
5. **时长格式化**：实现 `format_duration(seconds: float | int | None) -> str`，`None/0` 返回 `""`，`65` 返回 `"1m 5s"`，`3661` 返回 `"1h 1m 1s"`，不足 1 分钟仅显示秒。
6. **任务过滤**：实现 `filter_tasks(tasks: list[dict], keyword: str) -> list[dict]`，按 `name || filename` 含 `keyword` 子串过滤（大小写不敏感），空 `keyword` 返回原列表（模拟 `v-model` 搜索）。

## 延伸挑战

1. 在 `book/samples/vue-min` 中为 `App.vue` 增加 `v-model` 搜索框与 `status` 下拉（`pending/done/error`），用计算属性（`computed`）派生过滤列表，观察「数据源 `ref` → `computed` → `v-for`」的自动更新链路。
2. 把 `fetch('/mock.json')` 替换为 `fetch(import.meta.env.VITE_API_BASE_URL + '/tasks')`，并在 `vite.config.ts` 中加 `server.proxy` 将 `/api` 指向本地 `http://localhost:8000`，实现「开发走代理、生产走相对路径」的双环境切换。
3. 为 `vue-min` 增加 `vue-router`：`/` 列任务、` /task/:id` 详情，详情页用 `useRoute().params.id` 取参并 `fetch('/api/task/' + id)`，对比 `TasksListPage.vue` 的 `router.push('/transcript/' + t.id)` 导航。

> 本章内容原创，概念对应 MeetingToText 的 frontend/src/views/TasksListPage.vue 与 frontend/src/api/client.ts，示例代码与表述均为原创。
