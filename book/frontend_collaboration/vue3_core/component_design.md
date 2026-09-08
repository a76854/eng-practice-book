---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

# 组件设计

学完本节，你能回答：

- 一个"搜索框 + 结果列表"的页面，为什么要拆成多个组件，而不是写成一整页？
- Props 和 Emits 分别解决哪个方向的通信？谁往下传、谁往上通知？
- 前端在什么时候向后端发请求拉数据？这个时机由哪个钩子控制？
- 什么时候该抽一个组件，什么时候该抽一个组合函数？

响应式让单个页面内部"活"了起来。可一个文档搜索页，搜索框、结果列表、加载态、错误态都挤在一个文件里，越写越长，改一处要在整页里定位。这一节解决怎么把一个大页面拆成一块块零件，以及拆开的零件之间怎么说话。

> 组件像流水线上的标准零件：每个零件只认一种输入，做好了从固定口子把结果交出去，外壳不变、里面装的东西可以换。后端最熟的类比是：组件之于前端，如同函数之于后端，定义好参数和返回值，谁都能调、互不干扰。

这一节回答"界面怎么拆、拆开的零件怎么通信"，并在末尾补上联调真正的落点"数据什么时候拉"。一共四件事：为什么拆、往下传、往上通知、何时拉数据。

## 为什么要把页面拆成组件

把"搜索框 + 结果列表 + 加载态 + 错误态"全写在一个文件里，是这个页面最真实的模样：改一处请求逻辑要在整页代码里定位，想把结果卡片复用到收藏页就只能复制粘贴。组件把职责切成小块，每块自带输入输出，能独立看、独立改、独立复用。

文档搜索页天然能切成三块：一个 `SearchBar` 负责输入关键词并触发搜索，一个 `ResultCard` 负责把一条结果画成卡片，外面的父组件 `SearchView` 负责统筹"当前关键词是什么、结果有哪些"。三块各自清楚，后面对接后端、加缓存、加收藏按钮，都只动对应那一块。

## `Props`

父组件通过 Props 把数据传给子组件，子组件拿到的是只读副本，自己不能改。这对应后端的"函数参数"：调用方传入，接收方只读。

```vue
<!-- 父组件 SearchView.vue：把一条结果传给子组件 -->
<ResultCard :result="results[0]" />

<!-- 子组件 ResultCard.vue：声明自己认哪些输入，只读展示 -->
<script setup>
defineProps({ result: Object })
</script>

<template>
  <p>{{ result.title }}</p>
  <p>{{ result.source }}</p>
  <a :href="result.url">查看原文</a>
</template>
```

数据只能从父往子流动，这就是单向数据流。子组件若想改数据，不能直接改 Props，得走下面的 Emits。

顺带解开一个疑团：`defineProps` 不需要 `import` 就能用，是因为它是 `<script setup>` 的编译宏，由编译器在打包时处理，本身不是一个要 import 的函数。读 `<script setup>` 里那些 `defineXxx` 开头的东西，都按这个思路理解。

## `Emits`

子组件不该直接改父组件的状态，而是发一个事件通知父组件，由父组件决定怎么改。这对应后端的"回调"：子组件只上报，不越权。

```vue
<!-- 子组件 SearchBar.vue：发出 update:query 事件 -->
<script setup>
defineEmits(['update:query'])
</script>

<template>
  <input type="text" :value="query" @input="$emit('update:query', $event.target.value)" />
  <button @click="$emit('search')">搜索</button>
</template>

<!-- 父组件：监听事件，自己改状态 -->
<SearchBar :query="query" @update:query="query = $event" @search="doSearch" />
```

上一节讲过的 `v-model`，用在组件上就是上面这套"传值 + 监听 update"的语法糖：`<SearchBar v-model:query="query" />` 一行顶两行。等到你在项目里看到 `v-model:xxx`，要能认出它背后是"父传 Props、子发 update 事件"这一对。

还有一种"父想往子组件里塞一段自定义内容"的场景，比如结果卡片的操作区想由父组件指定。这种需求用插槽：子组件留一个 `<slot>` 占位，父组件把内容填进去。默认插槽已覆盖绝大多数场景，命名插槽、作用域插槽等真用到时再查文档即可。

## 生命周期

这是后端联调最该记住的一点。组件从"被创建"到"从页面消失"会经过几个阶段，最常用的两个钩子是：

```vue
<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'

const results = ref([])
const loading = ref(false)

onMounted(async () => {
  // 组件挂载到页面后执行一次，通常在这里拉后端数据
  loading.value = true
  results.value = await fetch('/api/search?q=pydantic').then(r => r.json())
  loading.value = false
})

onBeforeUnmount(() => {
  // 组件从页面移除前执行，用来清理定时器、取消请求
})
</script>
```

记住 `onMounted` 就够了：**前端就是在组件挂载之后，通过 `onMounted` 里的 `fetch` 去调你的接口。** 这也是联调时判断"这行请求是页面一进来就发，还是点了按钮才发"的根据。

## 抽组件还是抽组合函数

一块逻辑该放哪，看它有没有界面：

| 场景 | 抽什么 | 例子 |
| --- | --- | --- |
| 有界面结构要复用 | 组件 | `ResultCard`、`SearchBar` |
| 无界面、纯逻辑要复用 | 组合函数 | `useSearch`、`usePolling` |
| 两者都有 | 组件包裹组合函数 | `SearchView` 里用 `useSearch` |

原则一句话：界面复用抽组件，逻辑复用抽组合函数，两者都要就把逻辑装进组件里的组合函数。前面讲过的 `useSearch` 就是"纯逻辑"那一边的典型。

## 本节小结

- 组件是"带契约的部件"：按职责划边界，靠输入输出通信，能独立复用与演进。
- Props 向下只读传数据，Emits 向上发事件通知，一套单向数据流覆盖父子通信。
- `onMounted` 是前端向后端拉数据的标准时机，`onBeforeUnmount` 用来清理。
- 界面复用抽组件，逻辑复用抽组合函数，两者结合即"组件包裹组合函数"。

金句：组件把一页大代码拆成一盒零件，每个零件签好输入输出的契约，拼装和改动才不用再为一整页提心吊胆。
