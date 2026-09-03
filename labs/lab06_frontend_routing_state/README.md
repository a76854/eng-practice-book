# 实验六 前端页面开发与路由状态管理

> 对应理论 [第7章 前端开发概况与工程化演进](../../book/frontend_collaboration/frontend_overview/index.md) 与 [第8章 Vue3 核心机制与状态设计](../../book/frontend_collaboration/vue3_core/index.md) · 6 学时 · 任务说明与验收标准同 `book/lab_guide/frontend_routing_state/index.md`

## 实验目标

- 用 Vue3 组合式 API 组织会议记录面板，掌握模板与响应式的协作。
- 用 Vue Router 实现页面路由与登录拦截，理解守卫执行顺序。
- 用 Pinia 管理登录态与记录列表，体会前端状态与后端真相的边界。
- 在无后端时用 mock 保证可演示，后续可平滑替换为真实接口。

## 任务步骤

### 步骤 1 阅读理论

通读第7章 7.2 至 7.4 节与第8章 8.1 至 8.4 节，关注工程基石、响应式、路由与 Pinia。

### 步骤 2 读懂骨架

进入 `starter/`，阅读 `package.json`、`src/main.js`、`src/router/index.js` 与 `src/stores/` 的分层。

### 步骤 3 会议记录面板

完善 `Records.vue` 的搜索、列表与新增表单，逻辑收敛在 `records` Store 的 Getter 与 Action。

### 步骤 4 登录与路由拦截

完善 `auth` Store 的 `localStorage` 持久化，在路由守卫中对 `requiresAuth` 做拦截与重定向。

### 步骤 5 联调与边界

验证未登录拦截、登录后列表、搜索与新增、刷新保持等闭环，覆盖空输入与网络回退。

### 步骤 6 自检

确认 `package.json` 可解析、入口 JS 可解析、`npm install && npm run dev` 文档可复现、`git status` 干净。

## 验收标准

- [ ] 入口注册 Pinia 与 Router，`App.vue` 含 `<router-view />` 与登录态导航。
- [ ] 路由表与守卫生效，未登录访问受保护路由被拦截。
- [ ] `auth` Store 持久化登录态，`records` Store 管理列表与派生过滤。
- [ ] 无后端可演示，空与加载状态可区分，提交与搜索即时生效。
- [ ] 文档中的安装与启动命令可复现，仓库干净。

## 提交要求

提交 `starter/package.json`、`index.html`、`vite.config.js`、`src/` 与 `README.md`，写清安装、启动与构建命令。以演示与讨论验收。

## 预估用时

6 学时。

## 起手代码

见 `starter/` 目录。先阅读 `src/stores/` 与 `src/router/` 的分层，再按实验文档补齐面板、登录与守卫。
