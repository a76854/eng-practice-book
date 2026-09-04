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
- 三者如何共同撑起前端运行时 + 包管理 + 模块系统三件套？一个真实的前端工程长什么样？

上一节里 Vite 承担了构建这件事，但构建工具本身跑在哪里、依赖怎么装、源码怎么变成浏览器能跑的页面，还没有回答。这一节补上前端工程化的三件地基。

> 后端的三件套是 Python、pip、import：Python 是解释器，pip 装依赖，import 组织模块。前端有一套镜像版的三件套：Node 是前端的解释器，npm/pnpm 是前端的 pip，ES Module 是前端的 import。把这三件看清，前端工程就从黑箱变回了你熟悉的样子。

这一节把前端工程化落成三件可对照后端理解的事，最后用一个真实前端的目录骨架收口，兑现以后端视角读懂前端工程这个学习目标。

## 前端的运行时与工具宿主

Node 基于 V8 引擎，让 JavaScript 离开浏览器，在命令行和服务端运行。在前端工程里，Node 的角色不是替代浏览器，而是承载构建与开发工具：Vite 开发服务器、`vue-tsc` 类型检查、Rollup 打包以及各种脚本，全都跑在 Node 上。

```bash
node -v        # 运行时版本，对应 python -V
npm -v         # 包管理器版本
node app.js    # 运行 JS，对应 python app.py
```

对后端开发者最省力的直觉，是把 Node 理解成前端的 Python 解释器，把 `package.json` 理解成前端的 pyproject.toml。这一层对应关系，是入门最快的路标。

## npm / pnpm

### npm 的演进与痛点

- 早期 npm 用嵌套结构：每个包各自嵌套 `node_modules`，同一依赖的多版本重复落盘，路径深、装得慢。
- npm 3 起改扁平：尽量把依赖提升到顶层、减少重复，但也可能产生幽灵依赖：某个包并未声明，却因为被提升到顶层而能被 `import` 到。
- lockfile 出现后，`package-lock.json` 记录精确版本与完整性哈希，保证可复现；CI 里用 `npm ci` 严格按 lockfile 安装，而不是重新解析语义化版本。

### pnpm 的两点解法

pnpm 用内容寻址存储 + 符号链接同时解决省空间与严格依赖两个痛点：

- 省空间：同一版本在全局 store 只存一份，各项目的 `node_modules` 只是指向 store 的符号链接，十个项目共用一份 `vue@3.5.13`。
- 严依赖：项目的 `node_modules` 只暴露自己声明的依赖，幽灵依赖在 pnpm 下会直接报 `MODULE_NOT_FOUND`，逼着依赖声明更诚实。

```bash
npm install      # 按 package.json 解析安装（或 npm ci 严格按 lockfile）
pnpm install     # 按 pnpm-lock.yaml 安装，复用全局 store
```

不管是 npm 还是 pnpm，都应提交 lockfile。它如同后端提交的依赖锁文件，是依赖可复现的唯一事实源，缺了它，安装结果就成了在我机器上能跑。

## ES Module

CommonJS 用 `require` 在运行时动态加载，工具很难在不执行代码时判断哪些导出真正被用了。ES Module 用静态的 `import` / `export` 声明依赖：`import` 必须在顶层、路径是字符串字面量，工具因此在构建期就能静态分析出依赖图。

```javascript
// ESM：静态、可被 tree-shaking（未使用的导出可被剔除）
// 文件 utils/format.js
export function formatDuration(sec) { return `${sec}s` }
export function formatDate(d) { return d.toISOString() }

// 文件 app.js 只用了 formatDuration，formatDate 可被摇掉
import { formatDuration } from './utils/format.js'
console.log(formatDuration(42))
```

Vite 与 Rollup 正靠这个静态性做两件事：开发期按需服务（浏览器原生支持 `import`），生产期 tree-shaking（未被引用的 `formatDate` 不会进入 `dist/`）。`package.json` 里的 `"type": "module"`，就是声明本包按 ESM 解析。

## 工程化文件夹样例

三件套落地后，一个前端工程的后端视角地图大致是这样：

```text
frontend/
├── package.json           # 依赖与脚本
├── pnpm-lock.yaml         # 依赖锁
├── node_modules/          # 安装的依赖
├── src/
│   ├── main.ts            # 入口，装配应用
│   ├── App.vue            # 根组件
│   ├── components/        # 可复用组件
│   └── router/            # 前端路由
├── index.html             # 唯一真正的 HTML 入口
└── dist/                  # vite build 产物
```

和 [工程化项目结构](../../software_engineering/dev_meta_skills/engineering_project_structure.md) 里的 `pyproject.toml` + `src` 布局对照，你会看到同一套运行时 + 包管理 + 模块的影子：前端的 `package.json` + lockfile + `type: module`，正是后端的 `pyproject.toml` + lockfile + `import`。读懂这张地图，后端开发者就能参与前端的依赖评审与构建产物审计，这正是后续部署一章里 `dist/` 静态托管的起点。

## 本节小结

- Node.js 是前端的Python 解释器与工具宿主，Vite、`vue-tsc`、Rollup 都跑在它上面。
- npm/pnpm 解决依赖地狱与可复现：pnpm 用内容寻址 store 省空间、用严格依赖逼诚实，lockfile 是可复现的唯一事实源。
- ES Module 的静态 `import` / `export` 让工具不执行代码即可分析依赖图，是 tree-shaking 与按需加载的前提。
- 三者共同构成前端的运行时 + 包管理 + 模块系统，与后端的 Python + pip + import 形成镜像。

读不懂工程的代码库，工程对你就是一堆文件；看懂运行时、依赖、模块三件事，那些文件就自动排成了你知道的样子。