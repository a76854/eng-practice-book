# 实验六 前端页面开发与路由状态管理

本实验对应理论 [第7章 前端开发概况与工程化演进](../../part3_frontend_collaboration/chapter07_frontend_overview/index.md) 与 [第8章 Vue3 核心机制与状态设计](../../part3_frontend_collaboration/chapter08_vue3_core/index.md)。建议先通读第7章 7.2 至 7.4 节的框架选型与工程基石，再通读第8章 8.1 至 8.4 节的响应式、组件化、路由与 Pinia，最后参考 `labs/lab06_frontend_routing_state/starter/` 的起手骨架，再动手。你会在本实验中用 Vue3 + Pinia + Vue Router 完成会议记录管理面板、登录态保持与路由拦截的闭环。

## 实验目标

- 能用 Vue3 组合式 API 与单文件组件组织页面，理解 `ref` / `computed` / `watch` 与模板渲染的协作。
- 能用 Vue Router 声明前端路由，实现页面切换、动态参数与全局前置守卫的登录拦截。
- 能用 Pinia 按领域拆分状态，把“会议记录列表”与“登录态”分别收敛到独立 Store，实现跨组件共享与持久化思路。
- 能说清前端状态与后端真相的边界，解释为何以接口为权威、以前端为缓存，以及乐观更新失败时的回滚策略。
- 能在无后端的情况下用本地 mock 保证面板可演示，并说清后续如何把 `fetch('/mock.json')` 替换为真实接口。

## 任务步骤

### 步骤 1 阅读理论与现状

1. 阅读 [第7章 7.2 框架三驾马车](../../part3_frontend_collaboration/chapter07_frontend_overview/7.2_framework_troika.md) 至 [7.4 前端工程化基石](../../part3_frontend_collaboration/chapter07_frontend_overview/7.4_frontend_engineering_foundation.md)，理解 Vue3 在本课程中的选型理由与 `package.json` 的工程化作用。
2. 阅读 [第8章 8.1 响应式原理](../../part3_frontend_collaboration/chapter08_vue3_core/8.1_reactivity_principles.md) 至 [8.4 跨组件状态管理 Pinia](../../part3_frontend_collaboration/chapter08_vue3_core/8.4_cross_component_state_pinia.md)，重点关注组合式 API、路由守卫执行顺序与 Pinia 的 State / Getter / Action 三层。
3. 在本地打开 `labs/lab06_frontend_routing_state/starter/`，运行 `cat package.json` 与 `cat src/App.vue`，观察其 `fetch('/mock.json')` 回退与 `v-for` 渲染的最小闭环。

> 环境约定：本书面向 Linux，`npm` / `vite` 在 Linux 上命令一致，路径示例统一写 `/`。虚拟环境与 Node 环境相互独立，前端依赖通过 `package.json` 声明。

### 步骤 2 读懂起手骨架

1. 进入 `labs/lab06_frontend_routing_state/starter`，阅读 `README.md` 与 `package.json`，确认依赖含 `vue`、`pinia`、`vue-router`，脚本含 `dev`、`build`、`preview`。
2. 打开 `index.html`、`src/main.js`、`src/App.vue`、`src/router/index.js`、`src/stores/auth.js` 与 `src/stores/records.js`，梳理“入口、路由表、Store、视图”四层的依赖方向。
3. 用编辑器检查 `src/views/Login.vue` 与 `src/views/Records.vue` 的模板与脚本，留意登录表单如何调用 `auth` Store，列表页如何从 `records` Store 取派生数据并渲染。

### 步骤 3 实现会议记录管理面板

1. 以 `Records.vue` 为起点，完善会议记录面板：
   - 顶部为搜索框与刷新按钮，搜索基于 `records` Store 的 `keyword` 与 `filtered` Getter，输入即过滤。
   - 中间为 `v-for` 列表，展示文件名、标题与状态，空列表与加载中分别有独立文案。
   - 底部为“新增记录”表单，含标题与文件名输入，提交后调用 `records` Store 的 `addRecord` Action，列表即时更新。
2. 保持组件轻薄：视图只做展示与事件转发，数据与过滤逻辑收敛在 Store 的 Getter 中，列表排序与统计由 `computed` 派生。
3. 无后端时依赖 `public/mock.json` 与 `fetch` 回退，保证 `npm run dev` 后页面可直接演示。

### 步骤 4 实现登录态保持与路由拦截

1. 完善 `src/stores/auth.js` 的登录态：
   - State 含 `token` 与 `user`，初始从 `localStorage` 恢复。
   - Action 含 `login(username, password)` 与 `logout()`，`login` 写入 `localStorage`，`logout` 清理并重置。
   - Getter 含 `isAuthed`，供路由守卫与导航栏判断。
2. 在 `src/router/index.js` 中配置路由表与全局前置守卫：
   - 路由至少含 `/login` 与 `/records`，根路径重定向到 `/records`。
   - `requiresAuth` 标记需要登录的路由，守卫中若 `!auth.isAuthed` 则重定向到 `/login`。
   - 登录页若已登录则重定向回 `/records`，避免重复登录。
3. 在 `App.vue` 的导航栏中根据 `auth.isAuthed` 切换“登录 / 退出”按钮，退出后回到登录页。

### 步骤 5 联调与边界处理

1. 在浏览器中验证完整闭环：未登录访问 `/records` 被拦到 `/login`，登录后进入列表，搜索与新增即时生效，刷新后登录态仍保持。
2. 覆盖边界：空搜索、空标题提交、重复文件名、网络失败回退等场景，确认提示文案可读且不抛未捕获异常。
3. 在 `records` Store 的 `load` Action 中保留 `fetch('/mock.json')` 的回退思路，并注释后续如何替换为 `fetch('/api/records')` 的真实接口。

### 步骤 6 自检与清理

1. 运行 `python -c "import ast, json, pathlib; json.loads(pathlib.Path('starter/package.json').read_text()); print('package.json ok')"` 确认 `package.json` 可被解析，运行 `node --check starter/src/main.js` 或等价语法检查确认入口可解析。
2. 按 `starter/README.md` 的说明验证 `npm install && npm run dev` 的文档路径可复现，确认 `index.html` 含 `id="app"` 挂载点与 `src/main.js` 引用。
3. 用 `git status` 确认无 `node_modules/`、`dist/`、`.venv`、`__pycache__` 等不应提交的内容，准备演示路由与状态的协作。

## 验收标准

逐条自查，全部勾选即视为完成：

- [ ] `starter/package.json` 含 `vue`、`pinia`、`vue-router` 依赖与 `dev` / `build` 脚本，`index.html` 含 `id="app"` 挂载点与 `type="module"` 入口。
- [ ] `src/main.js` 创建 Vue 应用并注册 Pinia 与 Router，`src/App.vue` 含 `<router-view />` 与基于登录态的导航。
- [ ] 路由表含 `/login` 与 `/records`，根路径重定向到 `/records`，全局前置守卫对 `requiresAuth` 生效，未登录访问受保护路由被重定向。
- [ ] `auth` Store 管理 `token` / `user`，登录写入 `localStorage`，刷新后仍保持，退出后清理。
- [ ] `records` Store 管理列表、搜索关键字与加载态，含 `filtered` 等 Getter 与 `load` / `addRecord` 等 Action，面板的搜索与新增即时生效。
- [ ] 面板在无后端时可演示，`fetch('/mock.json')` 失败时回退到内置 mock，空列表与加载中状态可区分。
- [ ] `package.json` 可被 JSON 解析，入口 JS 可被 `node --check` 解析，`git status` 干净，能口头解释前端状态与后端真相的边界。

## 提交要求

- 提交包含 `starter/package.json`、`starter/index.html`、`starter/vite.config.js`、`starter/src/` 与 `starter/README.md` 的目录，`README.md` 需写清 `npm install`、`npm run dev` 与构建命令。
- 不需要提交 `node_modules/`、`dist/`、`.venv`、`__pycache__` 等生成物。
- 以演示与讨论作为验收，能现场演示登录拦截、列表过滤与新增的闭环，并解释路由与 Pinia 的协作。

## 预估用时

6 学时。

建议分配：步骤 1 至 2 约 80 分钟，步骤 3 至 4 约 160 分钟，步骤 5 至 6 约 120 分钟。剩余时间用于自检与课堂讨论。
