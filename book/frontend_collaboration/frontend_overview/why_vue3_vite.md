---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

# 为何选择 Vue 3 + Vite

> 学完本节，你能回答：Vue 3 的组合式 API 解决了什么规模化痛点？Proxy 响应式与 Vue 2 的 `Object.defineProperty` 有何本质差异？Vite 为何在开发期比“先打包再服务”的传统链路更快？

## 选型是约束的匹配

承接 [7.2 框架三驾马车](framework_troika.md)，本课程为 MeetingToText 选 **Vue 3 + Vite**，因为三条约束可复盘：受众是后端背景，Vue 的 SFC 贴近 HTML，渐进增强心智低；项目是任务列表、搜索、音频播放等中等交互后台，组合式 API 比选项式更易复用状态逻辑；工程链路要可解释的快，Vite 开发期按需转译加生产期 Rollup 打包正好匹配。换成 React 或 Angular，约束不同则结论应变。

Vue 3 的两点能力与 Vite 的一点分工一句话带过：组合式 API 把同一关注点的状态与逻辑收拢到一个组合函数，复用靠普通函数而非 mixin；Proxy 代理整个对象，新增属性与数组索引无需 `Vue.set` 即可追踪，细节见 [8.1 响应式原理](../vue3_core/reactivity_principles.md)；Vite 开发期不打包，生产期再用 Rollup 打包。

## 先动手：用 `vite build` 观察按需与打包的分工

下面用计数器类比 Vite 开发期只转译变更文件，传统链路需重打包全部文件。`vite build` 的分工在 `package.json` 脚本中可直接观察。

```javascript
// 示意：package.json（节选）
{
  "type": "module",
  "scripts": { "dev": "vite", "build": "vue-tsc --noEmit && vite build", "preview": "vite preview" },
  "dependencies": { "vue": "^3.5.13" },
  "devDependencies": { "vite": "^6.0.0", "@vitejs/plugin-vue": "^5.2.0" }
}
```

```
传统：源码 → 全部打包成 bundle → dev server 响应（改一行 → 增量重打包 bundle）
Vite： 源码 → ESM 按需服务 + 依赖预构建（esbuild），改一行 → 只转译该文件
```

```{code-cell} ipython3
# Vite 按需 vs 传统全量：改一文件需处理的文件数
files = ["App.vue", "router.ts", "store.ts", "utils.ts", "a.vue", "b.vue", "c.vue"]

def traditional_build(changed: str) -> int:
    return len(files)

def vite_dev(changed: str) -> int:
    return 1

for changed in ["App.vue", "store.ts"]:
    print(f"改 {changed}: 传统需处理 {traditional_build(changed)} 个文件, Vite 需处理 {vite_dev(changed)} 个文件")

assert vite_dev("App.vue") < traditional_build("App.vue")
print("构建对比通过：开发期按需显著少于全量")

# 观察 vite build 的脚本分工
import json
pkg = {"scripts": {"dev": "vite", "build": "vue-tsc --noEmit && vite build"}}
assert "vite" in pkg["scripts"]["dev"]
assert "vite build" in pkg["scripts"]["build"]
print("脚本分工：dev 用 vite 按需，build 用 vite build 产物到 dist/")
# 预期输出:
# 改 App.vue: 传统需处理 7 个文件, Vite 需处理 1 个文件
# 构建对比通过：...
# 脚本分工：...
```

观测小结：开发期 Vite 利用浏览器原生 ESM 按需转译，依赖用 esbuild 预构建缓存，改一行只转译一行；生产期 `vite build` 再走 Rollup tree-shaking 与分包，产物为优化后的静态资源。对后台系统，改列表过滤逻辑到热更新的反馈差异即来自该分工。

> **与后续章节的衔接**：本节的 Proxy 响应式将在 [第8章 响应式原理](../vue3_core/reactivity_principles.md) 展开；Vite 的生产构建与部署见 [第11章 部署与容器化](../../advanced_engineering/deploy_cicd/index.md)。

```bash
# 本地验证本节类比
.venv/bin/python -c "import json; pkg={'scripts': {'dev': 'vite', 'build': 'vue-tsc --noEmit && vite build'}}; print(pkg['scripts']['dev'])"
```
