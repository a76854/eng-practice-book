# Lab06 starter 说明

本目录是实验六的起点骨架，对应 `book/part5_lab_guide/experiment06_frontend_routing_state/index.md`。

## 包含内容

- `package.json`：Vue3 + Pinia + Vue Router 的最小声明，脚本含 `dev` / `build` / `preview`。
- `index.html`：挂载点 `id="app"` 与 `type="module"` 入口指向 `src/main.js`。
- `vite.config.js`：Vite + Vue 插件的最小配置，开发端口 5173。
- `src/main.js`：创建 Vue 应用，注册 Pinia 与 Router 后挂载。
- `src/App.vue`：顶部导航与 `<router-view />`，按登录态切换“登录 / 退出”。
- `src/router/index.js`：路由表 `/login` 与 `/records`，根路径重定向到 `/records`，全局前置守卫对 `requiresAuth` 做拦截。
- `src/stores/auth.js`：登录态 Store，`token` / `user` 读写 `localStorage`，提供 `isAuthed`、`login`、`logout`。
- `src/stores/records.js`：记录列表 Store，含 `records`、`keyword`、`filtered`、`doneCount`、`load`、`addRecord`，`fetch('/mock.json')` 失败回退内置 mock。
- `src/views/Login.vue`：登录表单，任意非空即可登录并跳转到 `/records`。
- `src/views/Records.vue`：会议记录面板，含搜索、刷新、列表与新增表单。
- `public/mock.json`：本地 mock 数据，保证无后端也能演示。

骨架保持“视图轻、Store 重、路由管拦截”的分层：视图只做展示与事件转发，状态与派生收敛在 Store，路由守卫集中处理鉴权。

## 运行命令

```bash
# 安装依赖（Windows / macOS / Linux 一致）
npm install

# 启动开发服务
npm run dev
# 打开 http://localhost:5173

# 构建
npm run build

# 预览构建产物
npm run preview

# 快速校验 JSON 与入口
python -c "import json, pathlib; json.loads(pathlib.Path('package.json').read_text()); print('package.json ok')"
node --check src/main.js
node --check src/router/index.js
node --check src/stores/auth.js
node --check src/stores/records.js
```

## 路由与状态提示

- 未登录访问 `/records` 会被全局守卫重定向到 `/login`，登录后自动回到 `/records`。
- `auth` Store 的 `token` 持久化在 `localStorage`，刷新后仍保持，退出则清理。
- `records` Store 的 `filtered` 为基于 `keyword` 的派生，搜索即过滤；`addRecord` 直接改本地列表，后续替换为 `fetch('/api/records')` 时可保持同一 Action 入口。

后续替换真实接口时，只需把 `records` Store 的 `load` 与 `addRecord` 中的 `fetch('/mock.json')` 改为真实 `fetch('/api/records')`，视图无需改动。

## 跨平台说明

- `npm` / `vite` 命令三平台一致，路径示例统一写 `/`。
- `index.html` 的 `type="module"` 固定写法，`pathlib.Path` 自动适配 `\`。

## 下一步

按实验文档步骤 3 至 5 完善面板的边界提示、登录失败文案与空列表状态，并在浏览器中验证登录拦截、搜索与新增的完整闭环。
