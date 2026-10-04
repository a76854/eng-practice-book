---
numbering: false
---

# 实验四 文档查询前端

本实验对应理论 [第 8 章 前端开发概况与工程化演进](../frontend_collaboration/frontend_overview/index.md) 与 [第 9 章 Vue3 核心机制与状态设计](../frontend_collaboration/vue3_core/index.md)。建议先通读 [前端工程化基石](../frontend_collaboration/frontend_overview/frontend_engineering_foundation.md)，再读 [响应式原理](../frontend_collaboration/vue3_core/reactivity_principles.md)、[路由管理](../frontend_collaboration/vue3_core/routing_management.md) 与 [跨组件状态管理 Pinia](../frontend_collaboration/vue3_core/cross_component_state_pinia.md)，最后参考 [组件测试](../frontend_collaboration/vue3_core/component_testing.md) 动手。

本实验不提供起始代码，你将从零建立一个 Vue3 项目，用五个任务完成搜索与收藏的完整前端。

## 实验目标

通过完成文档查询前端，你将：

1. **搭起前端工程**：用 Vite 建立 Vue3 项目，用 `package.json` 声明依赖与脚本，理解前端工程化的最小构成。
2. **用组合式组织组件**：用组合式 API 与单文件组件实现搜索页，理解 `ref`、`computed`、`watch` 与模板渲染的协作。
3. **用路由管理导航**：用 Vue Router 声明页面路由，并用全局前置守卫实现登录拦截。
4. **用 Pinia 收敛状态**：按领域拆分 Store，把登录态、文档列表与收藏分别收敛，实现跨组件共享与持久化。
5. **为组件写测试**：用 Vitest 覆盖三态与空列表等关键行为，并能在无后端时用本地 mock 完成演示。

## 背景故事

后端同学已经定好了接口清单，正在实现（见实验三）。前端这边不能干等，团队约定：先把界面做出来，用本地 mock 数据保证页面能跑、能演示，等接口就绪再把数据源切换过去。你负责搜索页、收藏页与登录页，并保证刷新后登录态还在、未登录进不去受保护页面。

## 预备知识

**接口清单**（与实验三一致，前端据此对齐）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/search?q=` | 按关键词检索文档，返回文档列表 |
| GET | `/api/favorites` | 列出已收藏的 `doc_id` |
| POST | `/api/favorites` | 收藏一篇文档，请求体 `{"doc_id": "..."}` |
| DELETE | `/api/favorites/{doc_id}` | 取消收藏 |
| POST | `/api/login` | 登录换取令牌，请求体 `{"username": "...", "password": "..."}` |

**数据形状**

- 文档：`{ id, title, source, url, content }`，`id` 即文档 URL。
- 登录响应：`{ token }`。

**目录约定**

```
src/
├── main.js          # 入口：创建应用，注册 Pinia 与 Router
├── App.vue          # 根组件：导航栏与 <router-view />
├── router/index.js  # 路由表与全局前置守卫
├── stores/          # auth.js、documents.js、favorites.js
└── views/           # Login.vue、Search.vue、Favorites.vue
public/
└── mock.json        # 本地回退数据
package.json         # 依赖与 dev/build 脚本
```

**环境约定**

- 前端依赖由本项目的 `package.json` 管理，与书仓的 Python 环境相互独立。
- 用 Vite 作为构建与开发服务器；环境约定为 Linux，路径统一写 `/`。

---

# 任务一：前端工程脚手架

## 任务目标

用 Vite 建立 Vue3 项目，配好路由与状态管理依赖，形成可运行的最小工程。

## 需求

1. 用 Vite 建立 Vue3 项目，`package.json` 含 `vue`、`pinia`、`vue-router` 依赖。
2. `package.json` 提供 `dev` 与 `build` 脚本。
3. `index.html` 提供 `id="app"` 挂载点与模块化入口。
4. `src/main.js` 创建应用并注册 Pinia 与 Vue Router。
5. `src/App.vue` 含 `<router-view />` 与一个导航区域。

## 验收标准

| 验收项 | 具体要求 |
|--------|----------|
| 依赖与脚本 | `package.json` 含三个依赖与 `dev` / `build` |
| 入口 | `index.html` 有挂载点，`main.js` 注册 Pinia 与 Router |
| 可运行 | `npm install && npm run dev` 能启动并渲染首页 |

## 提交要求

```bash
git switch -c exp/01-frontend-scaffold
git add package.json index.html vite.config.js src/
git commit -m "chore: scaffold Vue3 project with router and pinia"
git push -u origin exp/01-frontend-scaffold
```

---

# 任务二：登录页与登录态

## 任务目标

实现登录页，并用一个 Store 管理登录态，刷新后保持。

## 需求

1. 页面 `/login` 含用户名与口令输入与登录按钮。
2. `stores/auth.js` 的 State 含 `token` 与 `user`，初始从 `localStorage` 恢复。
3. `auth` 提供 `login(username, password)` 与 `logout()` 两个 Action：登录写入 `localStorage`，退出清理。
4. `auth` 提供 `isAuthed` 这个 Getter，供导航栏与路由守卫使用。
5. 登录成功后跳转到搜索页；登录失败给出可读提示。

## 验收标准

| 验收项 | 具体要求 |
|--------|----------|
| 登录可用 | 正确凭证登录成功并跳转，错误凭证有提示 |
| 持久化 | 刷新页面后登录态仍在，退出后清理 |
| Getter | `isAuthed` 反映当前登录状态 |

## 提交要求

```bash
git switch -c exp/02-login-state
git add src/views/Login.vue src/stores/auth.js src/App.vue
git commit -m "feat: add login page and persisted auth store"
git push -u origin exp/02-login-state
```

---

# 任务三：搜索页与文档状态

## 任务目标

实现搜索页，用组合式 API 与一个 Store 管理关键词、过滤结果与加载态。

## 需求

1. 页面 `/search` 顶部为搜索框，输入即过滤（无需点按钮）。
2. `stores/documents.js` 管理 `keyword`、原始列表、加载态与错误态，并提供一个派生过滤结果的 Getter。
3. 组件保持轻薄：视图只做展示与事件转发，过滤逻辑收敛在 Store 的 Getter 中。
4. 列表为空与加载中要有各自独立的文案，不能混在一起。
5. 每条结果提供“收藏”按钮，点击后触发收藏（本任务可先调用 mock，实验六联调时再接真实接口）。

## 验收标准

| 验收项 | 具体要求 |
|--------|----------|
| 交互即时 | 输入关键词后列表即时过滤 |
| 状态区分 | 空列表、加载中、错误三种状态各有文案 |
| 组件轻薄 | 过滤在 Store 的 Getter 中，组件不含过滤算法 |
| 组合式使用 | 使用 `ref` / `computed` / `watch` 组织逻辑 |

## 提交要求

```bash
git switch -c exp/03-search-page
git add src/views/Search.vue src/stores/documents.js
git commit -m "feat: add search page with keyword-driven filtering"
git push -u origin exp/03-search-page
```

---

# 任务四：收藏页与路由守卫

## 任务目标

实现收藏页与收藏状态，并用路由守卫把未登录用户挡在受保护页面之外。

## 需求

1. `stores/favorites.js` 管理收藏列表，提供加载、新增、删除等 Action 与判断是否已收藏的 Getter。
2. 页面 `/favorites` 展示已收藏文档，可取消收藏，列表随之更新。
3. 路由表含 `/login`、`/search`、`/favorites`，根路径重定向到 `/search`。
4. 需要登录的路由用 `requiresAuth` 标记，全局前置守卫在未登录时重定向到 `/login`。
5. 已登录时访问登录页应转回搜索页，避免重复登录。
6. 导航栏按 `isAuthed` 切换“登录 / 退出”，退出后回到登录页。

## 验收标准

| 验收项 | 具体要求 |
|--------|----------|
| 收藏可用 | 收藏与取消即时反映在收藏页 |
| 守卫生效 | 未登录访问受保护路由被重定向到 `/login` |
| 反向重定向 | 已登录访问登录页转回搜索页 |
| 导航联动 | 导航栏随登录态切换 |

## 提交要求

```bash
git switch -c exp/04-favorites-guard
git add src/views/Favorites.vue src/stores/favorites.js src/router/index.js src/App.vue
git commit -m "feat: add favorites page and route guard"
git push -u origin exp/04-favorites-guard
```

---

# 任务五：组件测试与本地回退

## 任务目标

为关键组件写测试，并保证无后端时页面仍可演示。

## 需求

1. 引入 Vitest，为搜索页与收藏页写组件测试。
2. 测试至少覆盖：输入关键词后过滤结果正确；空列表渲染空态；加载态渲染加载文案。
3. 页面数据请求在失败时回退到 `public/mock.json`，保证脱离后端可演示。
4. 在代码中注释说明，联调时如何把 mock 数据源切换为真实接口。

## 验收标准

| 验收项 | 具体要求 |
|--------|----------|
| 测试通过 | `npm run test` 全部通过 |
| 覆盖关键行为 | 过滤、空态、加载态均有测试 |
| 可脱机演示 | 无后端时页面能加载并展示 mock 数据 |
| 切换说明 | 注释说明真实接口的接入点 |

## 提交要求

```bash
git switch -c exp/05-component-test
git add src/ tests/ public/mock.json
git commit -m "test: add component tests and local mock fallback"
git push -u origin exp/05-component-test
```

---

# 综合验收标准

| 验收项 | 具体要求 |
|--------|----------|
| 工程化 | `package.json` 依赖与脚本完整，`npm run dev` / `build` 可用 |
| 组件 | 搜索页、收藏页、登录页三段式闭环可演示 |
| 状态 | 三个 Store 按领域拆分，登录态持久化生效 |
| 路由 | 页面路由与登录守卫正确，重定向双向生效 |
| 测试 | 组件测试通过，覆盖三态与空列表 |
| 可演示 | 无后端时用 mock 完成完整演示 |

---

# 实验报告要求

提交一份实验报告，包含：

1. **页面结构**：三个页面各自的功能与交互。
2. **状态设计**：三个 Store 的 State、Getter、Action 一览，以及为何这样拆分。
3. **守卫设计**：登录拦截与反向重定向的执行位置与顺序。
4. **测试说明**：覆盖了哪些行为，哪一处最难测。
5. **遇到的问题及解决过程**（至少 3 个）。
6. **实验收获与反思**。

---

# 评分参考

| 部分 | 分值 | 说明 |
|------|------|------|
| 任务一：工程脚手架 | 15% | 依赖、脚本、入口完整 |
| 任务二：登录与登录态 | 20% | 登录可用、持久化生效 |
| 任务三：搜索与文档状态 | 25% | 输入即过滤、三态区分、组件轻薄 |
| 任务四：收藏与路由守卫 | 25% | 收藏闭环、守卫双向生效 |
| 任务五：组件测试与回退 | 15% | 测试覆盖关键行为、可脱机演示 |
