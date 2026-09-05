---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

# 前端工程化基石

学完本节，你能回答：

- Node.js 在前端工程里承担什么角色？为什么它能被理解成前端的 Python 解释器？
- npm 与 pnpm 如何解决依赖地狱与可复现？pnpm 的严格依赖又是怎么一回事？
- ES Module 的静态结构，为什么让 tree-shaking 与按需加载成为可能？
- 三者如何共同撑起前端运行时 + 包管理 + 模块系统三件套？一个以 Vue 3 为例的真实前端工程长什么样？

上一节用 Vite 跑通了开发服务器，看到了热更新和构建产物的速度差异。但 Vite 本身跑在什么上面、依赖怎么装、源码怎么被解析成浏览器能跑的代码，还没有回答。这一节补上前端工程化的三件地基。

> 后端的三件套是 Python、pip、import：Python 是解释器，pip 装依赖，import 组织模块。前端有一套镜像版的三件套：Node.js 是前端的解释器与工具宿主，npm/pnpm 是前端的包管理器，ES Module 是前端的模块系统。把这三件看清，前端工程就从黑箱变回了你熟悉的样子。

这一节把前端工程化拆成三个对照后端的概念来讲：运行时、包管理、模块系统，最后用一个真实的前端目录骨架收口，让你能以后端视角读懂任何一个现代前端工程。

## Node.js

JavaScript 原本只能在浏览器里运行。2009 年，Node.js 基于 Chrome V8 引擎，把 JavaScript 带到了命令行和服务端。在前端工程里，Node.js 的主要角色不是替代浏览器，而是承载构建与开发工具：Vite 开发服务器、`vue-tsc` 类型检查、Rollup 打包、ESLint 检查，全都跑在 Node.js 上。

```bash
node -v        # 运行时版本，对应 python -V
npm -v         # 包管理器版本
node app.js    # 运行 JS，对应 python app.py
```

可以把 Node.js 理解成前端的 Python 解释器。Node.js 负责执行 `.js` 和 `.ts` 文件、驱动事件循环。两者都不是“语言的归宿”（Python 和 JavaScript 都可以脱离解释器运行在浏览器或嵌入式环境），只是是工程中最常用的运行时底座。

实际项目中，Node.js 版本管理通常用 `nvm`（Node Version Manager），功能类似 Python 的 `pyenv`：

```bash
nvm install 20   # 安装 Node 20，类似 pyenv install 3.12
nvm use 20       # 切换版本，类似 pyenv local 3.12
```

`package.json` 里的 `engines` 字段，指定了这个项目要求的 Node 版本，对应后端的 `requires-python = ">=3.8"`。

## npm / pnpm

包管理器解决的核心问题是：依赖从哪来、装到哪、版本怎么定、多项目怎么复用。

### npm 的演进与遗留问题

npm 是 Node.js 自带的包管理器，经历了三个重要版本，每次都在解决上一版本的痛点：

- **npm v2**：嵌套安装。每个包的依赖都放在自己的 `node_modules` 里，形成一棵嵌套的目录树。优点是每个包独立、不互相干扰；代价是目录深度惊人——`node_modules` 路径能深到超过 Windows 的路径长度限制，重复依赖的同一版本会在磁盘上存十几份。

- **npm v3**：扁平提升。尽量把依赖提升到顶层 `node_modules`，减少重复。多个版本冲突时，只有一个被提升，其他仍嵌套。目录变浅了，磁盘占用也小了，但引入了一个新问题：**幽灵依赖**。某个包并未在 `package.json` 中声明，却因为被提升到顶层，能被你的代码直接 `import` 到。这在后端世界相当于一个函数能直接调用 `requests`，但 `pyproject.toml` 里根本没写它。项目在本地能跑，换个环境就崩。

- **npm v5 及以后**：引入 `package-lock.json`。锁文件记录了每个依赖的精确版本和完整性哈希，保证在不同机器上安装出完全相同的 `node_modules` 结构。CI 里用 `npm ci` 严格按 lockfile 安装，而不是重新解析语义化版本范围。

### pnpm 的两点解法

pnpm 在 npm 的基础上做了两点关键改进，同时解决省空间与严格依赖两个问题：

**第一，内容寻址存储。** 所有依赖的同一版本在全局 store 里只存一份，各项目的 `node_modules` 只是指向 store 的硬链接或符号链接。十个项目共用一份 `vue@3.5.13`，磁盘占用从十份减到一份，安装速度也大幅提升。

**第二，严格的依赖隔离。** 项目的 `node_modules` 只暴露自己声明的依赖。如果你用了 `lodash` 但没在 `package.json` 里写它，代码里 `import` 时会直接报 `MODULE_NOT_FOUND`。这逼着依赖声明更诚实，也减少了“在我机器上能跑”的幻觉。

```bash
npm install      # 按 package.json 解析安装
npm ci           # 严格按 package-lock.json 安装（CI 专用）
pnpm install     # 按 pnpm-lock.yaml 安装，复用全局 store
```

不管是 npm 还是 pnpm，lockfile 都应提交到版本库。它如同后端的 `uv.lock`，是依赖可复现的唯一事实源。缺了它，安装结果就成了“在我机器上能跑”。

## ES Module

### 从 CommonJS 到 ES Module

Node.js 早期用 CommonJS 的 `require` / `module.exports` 组织模块。`require` 可以在运行时动态加载，路径可以是变量，可以在条件分支里调用。这意味着工具想分析“这段代码用了哪些依赖”，必须真正执行代码才能知道。

ES Module（ESM）用静态的 `import` / `export` 声明依赖。`import` 必须在模块顶层、路径必须是字符串字面量，不能放在 `if` 里、不能用变量拼接路径。这个限制让工具在**不执行代码**的情况下就能构建出完整的依赖图。

```javascript
// CommonJS：动态，工具无法静态分析
if (condition) {
  const utils = require('./utils.js')  // 运行时才决定
}

// ES Module：静态，工具一读文件就知道依赖关系
import { format } from './utils.js'   // 顶层、字面量
```

### 静态结构的三重收益

ES Module 的静态性，直接支撑了现代前端工具的三大能力：

**第一，Tree-shaking。** 打包工具从入口出发，沿依赖图追踪，标记所有被用到的导出。未被标记的代码（如从未被引用的函数）不会进入最终的 bundle。上面的例子中，`utils.js` 导出了 `formatDuration` 和 `formatDate`，但只有 `formatDuration` 被用到了，`formatDate` 在打包时会被剔除。

**第二，按需加载。** 动态 `import()` 虽然语法上允许动态路径，但它的本质是返回一个 `Promise`，告诉打包工具：这个模块在首次渲染时不加载，等到真正需要的时候再异步加载。在 Vite / Webpack / Rollup 中，这会自动触发代码分割（code splitting），生成单独的 chunk 文件。

**第三，开发期更快的启动速度。** Vite 利用浏览器原生支持 ESM 的特性，在开发期不打包所有代码，只按需转换请求的模块。修改一个文件时，只需要重新加载相关模块，而不需要重新打包整个应用。

`package.json` 里的 `"type": "module"`，就是声明本项目按 ESM 解析 `.js` 文件。如果没有这个字段，`.js` 默认按 CommonJS 处理。

## 三者的协作关系

Node.js、npm/pnpm、ES Module 三件套共同支撑起现代前端工程，它们的分工如下：

| 组件 | 职责 |
| --- | --- |
| Node.js | 执行 JS/TS 代码，驱动 Vite、vue-tsc、Rollup 等工具 |
| npm / pnpm | 管理依赖版本，从 npm registry 下载包，处理依赖冲突与复用 |
| ES Module | 组织模块依赖，让构建工具能静态分析、按需加载、摇掉无用代码 |

三者的关系可以这样理解：Node.js 提供了执行环境，npm/pnpm 提供了依赖资源，ES Module 提供了模块引用的语法规范。缺任何一个，前端工程都没法运作：

- 没有 Node.js，`vite`、`vue-tsc` 这些工具根本跑不起来
- 没有 npm/pnpm，项目依赖的 Vue、Vite、路由库都装不上
- 没有 ES Module，Vite 无法做 tree-shaking，开发期无法按需转换模块

## 工程化文件夹样例

三件套落地后，一个以 Vue 3 + Vite + pnpm 为技术栈的前端工程，目录结构大致是这样：

```text
frontend/
├── package.json                # 项目元信息 + 依赖声明
├── pnpm-lock.yaml              # 依赖锁文件
├── .npmrc                      # pnpm/npm 配置
├── node_modules/               # 实际安装的依赖
├── .vscode/                    # VS Code 工作区配置
│   └── settings.json           # 编辑器格式化、保存时自动 lint
├── public/                     # 静态资源
│   └── favicon.ico
├── src/
│   ├── main.ts                 # 应用入口：创建 Vue 实例、挂载到 #app
│   ├── App.vue                 # 根组件：布局、路由出口、全局样式
│   ├── components/             # 可复用组件
│   │   ├── WeatherCard.vue     # 天气展示卡片
│   │   └── ErrorToast.vue      # 错误提示组件
│   ├── views/                  # 页面级组件
│   │   ├── WeatherView.vue     # /weather 页面
│   │   └── AboutView.vue       # /about 页面
│   ├── router/
│   │   └── index.ts            # 前端路由配置：路径 → 组件映射
│   ├── stores/                 # Pinia 状态管理
│   │   └── weather.ts          # 天气数据的 store
│   ├── api/                    # 接口调用层（封装后端 API）
│   │   └── weather.ts          # fetch('/api/weather/...') 封装
│   ├── utils/                  # 工具函数
│   │   └── format.ts           # 格式化函数
│   └── types/                  # TypeScript 类型定义
│       └── weather.ts          # 后端接口响应的类型定义
├── index.html                  # 唯一真正的 HTML 入口
├── vite.config.ts              # Vite 构建配置
├── tsconfig.json               # TypeScript 编译配置
├── tsconfig.node.json          # Node.js 环境下的 TS 配置
├── env.d.ts                    # 环境变量的类型声明
└── dist/                       # 构建产物
    ├── index.html
    └── assets/
        ├── index-abc123.js
        ├── index-def456.css
        └── vendor-ghi789.js
```

### 逐层解读

**根目录文件**：`package.json` + `pnpm-lock.yaml` 组合，对应后端的 `pyproject.toml` + `uv.lock`。`package.json` 里的 `scripts` 字段是前端常用命令的入口，对应后端的 `Makefile` 或 `[project.scripts]`：

```json
{
  "scripts": {
    "dev": "vite",           // pnpm run dev → 启动开发服务器
    "build": "vue-tsc && vite build",  // pnpm run build → 类型检查 + 构建生产包
    "preview": "vite preview"          // 本地预览构建产物
  }
}
```

**`src/` 目录**：前端的业务代码，对应后端的 `src/`。`main.ts` 是入口，`App.vue` 是根组件。`components/`、`views/`、`router/`、`stores/`、`api/`、`utils/` 的分层，对应后端的分层架构——数据层（`api/`）、业务层（`stores/`）、视图层（`components/` 和 `views/`）、路由层（`router/`）。

**`index.html`**：前端的“唯一真相来源”。浏览器首次加载的是这个文件，它引用 `main.ts`（通过 `<script type="module">`），Vite 在开发期从它开始构建依赖图。

**`vite.config.ts`**：构建工具的配置，对应后端的 `pyproject.toml` 里 `[tool.ruff]` 这类工具配置。常见的 Vite 配置包括：开发代理（`/api` 转发到后端）、别名（`@` 指向 `src/`）、插件（Vue 插件、压缩插件）。

**`tsconfig.json`**：TypeScript 编译器的配置，规定输出目标、模块解析策略、路径映射。它的角色类似后端的 `pyproject.toml` 里 `[tool.mypy]` 的内容。

## 本节小结

- Node.js 是前端的解释器与工具宿主，Vite、vue-tsc、Rollup 都跑在它上面。类比后端的 Python 解释器。
- npm/pnpm 解决依赖管理：npm 从嵌套到扁平再到锁文件，pnpm 用内容寻址省空间、用严格依赖逼声明更诚实。lockfile 是依赖可复现的唯一事实源，类似后端的 `uv.lock`。
- ES Module 的静态 `import` / `export` 让工具不执行代码即可分析依赖图，支撑了 tree-shaking、按需加载和 Vite 的按需转换。
- 三件套共同构成前端的运行时 + 包管理 + 模块系统，与后端的 Python + pip/uv + import 形成镜像。
- 一个 Vue 3 + Vite + pnpm 工程的目录结构，从 `package.json` 到 `src/` 到 `dist/`，与后端的 `pyproject.toml` + `src/` 形成结构上的对照。
