---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

# Vue 3 与 Vite

学完本节，你能回答：

- Vue 3 的核心特性（单文件组件、声明式渲染、响应式、组件化）分别解决什么问题？
- 什么是组合式 API？它和选项式 API 在组织代码上有什么区别？
- 为什么前端需要 Vite？它在开发期与生产期各承担什么角色？

上一节对比了三大框架。这里我们不争论谁更好，本书选择 Vue 3，配套的构建工具是 Vite，讲解一下前端

> 去罗马的路有很多，现在你要做的事不是挑选一条近的路，先走吧。走了才知道哪条路更适合你。

本节不考虑选型，不讨论哪个框架更好^[小孩子才做选择，我全都要]，有什么优势，做的是就是简单介绍一下Vue3（读法view three^[如果你熟悉拼读的话，你能猜到vue的读音同view]），它有哪些能力、怎么组织代码、需要什么工具才能跑起来。后面的其他事情，只能靠各位读者自己探索了。

## Vue 3 是什么

Vue 3 是一个用于构建用户界面的 JavaScript 框架。它的核心思想很简单：用**声明式**的方式描述界面长什么样，把数据如何变成界面交给框架自动维护。一个最小组件长这样：

```vue
<!-- 一个单文件组件（SFC）：模板、逻辑、样式同处一个 .vue 文件 -->

<!--声明逻辑-->
<script setup>
import { ref } from 'vue'
const count = ref(0)
</script>

<!--这部分用于声明排版-->
<template>
  <button @click="count++">点了 {{ count }} 次</button>
</template>

<!--下面的声明样式-->
<style scoped>
button { padding: 8px 16px; }
</style>
```

围绕这个最小例子，可以看出 Vue 3 的几项核心特性：

| 特性 | 解决什么 | 在上例中的体现 |
| --- | --- | --- |
| 单文件组件（SFC） | 一个组件一个文件，模板、逻辑、样式聚在一处 | `<template>` 与 `<script>` 同在一个 `.vue` 文件^[当然，vue3的开发者不傻，为了工程的可维护性，肯定能拆分，分别定义然后import。这里就是一个示例] |
| 声明式渲染 | 只描述什么数据长什么样，不手写 DOM | `{{ count }}` 声明了这里显示计数的值 |
| 响应式 | 数据一变，界面自动更新，无需手动同步 | `count++` 后按钮文字自动跟着变 |
| 组件化 | 把界面拆成可复用的部件，用 props/emit 通信 | 这个按钮组件可被反复引用 |
| 指令 | 用 `v-if`/`v-for`/`v-model` 表达条件、循环、双向绑定 | `@click` 绑定了点击事件 |

这些特性共同把命令式地改 DOM升维成声明式地描述状态到视图。这就是框架在上一个演进阶段解决的核心问题。

## 组合式 API

Vue 3 提供两种组织组件逻辑的方式：选项式 API 与组合式 API。

选项式 API 按选项切分：数据、方法、计算属性分别散落在 `data`、`methods`、`computed` 三块里。单个功能好读，但一个组件同时管列表加载、搜索过滤、播放状态时，同一个关注点的逻辑就被选项割裂到文件各处。

组合式 API 反过来按关注点收拢：把同一件事的状态与逻辑放进一个组合函数，复用靠普通函数而非混入。对照如下：

```javascript
// 选项式（Vue 2 风格）：同一关注点被选项割裂
export default {
  data() { return { keyword: '', tasks: [] } },
  methods: { search() { /* 过滤逻辑 */ }, load() { /* 拉取逻辑 */ } },
  computed: { filtered() { return this.tasks.filter(/* ... */) } }
}
```

```javascript
// 组合式（Vue 3 风格）：按关注点收拢，可抽成 useTaskList()
import { ref, computed } from 'vue'

function useTaskList() {
  const keyword = ref('')
  const tasks = ref([])
  const filtered = computed(() => tasks.value.filter(t => t.filename.includes(keyword.value)))
  return { keyword, tasks, filtered }
}
// 组件里一行引入：const { keyword, tasks, filtered } = useTaskList()
```

同一份搜索过滤逻辑，组合式把它收进了一个可复制、可测试的 `useTaskList()`。当它要跨组件复用时，前者要复制一堆散落的字段，后者只需调用同一个函数。`ref` 包装出一个响应式数据，`computed` 声明一个由其他状态推导出来的派生值，这两者是组合式 API 里最常用的两个原语。

## Proxy 响应式：把改数据即改视图补圆

响应式是数据一变界面自动变的幕后在起作用的东西。Vue 2 用 `Object.defineProperty` 拦截属性，但有两个盲区：对象新增属性时追踪不到、数组通过索引改值时也追踪不到，需要 `Vue.set` 之类的补丁。Vue 3 改用 Proxy 代理整个对象，任何属性读写都能被拦截，新增属性、数组索引统统不再需要补丁。

```javascript
// Vue 2 的盲区需要补丁
// this.tasks[0] = newTask                 // 视图不更新
// this.$set(this.tasks, 0, newTask)       // 必须显式补丁

// Vue 3 的 Proxy 代理整个对象
// state.tasks[0] = newTask                // 视图自动更新，无需补丁
```

响应式背后的完整实现，放到后续的响应式原理一节展开。这里只需记住一句结论：代理整个对象，比逐个属性打补丁更不易漏。

## 为什么需要 Vite

浏览器不认识 `.vue` 文件，也不懂 `import` 来的依赖要从哪里解析，更不会自己压缩、摇树以缩小体积。所以前端源码不能直接丢给浏览器，必须经过一道构建。Vite 就是承担这道工序的工具。

它把开发期与生产期拆成两条策略：

```json
# package.json 的脚本分工（示意）
"scripts": {
  "dev": "vite",                              # 开发期：按需服务
  "build": "vue-tsc --noEmit && vite build",  # 生产期：类型检查 + 打包
  "preview": "vite preview"                   # 本地预览构建产物
}
```

| 阶段 | 策略 | 目标 |
| --- | --- | --- |
| 开发期 | 浏览器原生 ESM 按需转译单文件 + esbuild 预构建依赖 | 改一行、瞬时可见 |
| 生产期 | Rollup 做 tree-shaking 与分包 | 产物最小、可缓存 |

开发期像咖啡馆现磨：你要哪一杯就磨哪一杯，依赖是提前备好的材料；生产期像工厂灌装：统一优化、去冗余、分包装箱。传统构建工具把两件事都用先打包再服务一条流水线做，改一行也要重新增量打包整个 bundle，Vite 则把两条拆开，这是它在开发期明显更快的原因。

## 本节小结

- 本书以一个具体框架（Vue 3）为载体来讲前端：用声明式描述界面、用响应式自动同步，把状态到视图交给框架。
- Vue 3 的核心特性是单文件组件、声明式渲染、响应式、组件化与指令，它们共同把手改 DOM升维成描述状态到视图。
- 组合式 API 按关注点组织代码，用 `ref` 与 `computed` 把可复用逻辑收进普通函数，替代按选项割裂的写法。
- 前端源码不能直接被浏览器运行，所以需要 Vite：开发期按需转译、图快，生产期打包优化、图小。

学框架的最好方式不是比较它，而是把它用熟；用一个具体的框架，把状态如何变成视图这一件事练透，换到任何一个框架都能举一反三。