---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

# 把界面拆成组件

学完本节，你能回答：

- 一个“搜索框 + 列表”的页面，为什么要拆成多个组件，而不是写成一整页？
- Props 和 Emits 分别解决哪个方向的通信？谁往下传、谁往上通知？
- 前端在什么时候向后端发请求拉数据？这个时机由哪个钩子控制？
- 什么时候该抽一个组件，什么时候该抽一个组合函数？

上一节讲清了响应式：数据一变，视图跟着变。但真实的页面不可能是一段脚本从头写到尾，界面要拆成一块块可复用的部件，每块有清晰的输入与输出。这一节讲怎么拆、拆开的部件之间怎么说话。

> 组件像流水线上的标准零件：每个零件只认一种输入，做好了从固定口子把结果交出去，外壳不变、里面装的东西可以换。后端最熟的类比是：组件之于前端，如同函数之于后端，定义好参数和返回值，谁都能调、互不干扰。

这一节回答“界面怎么拆、拆开的零件怎么通信”，并在末尾补上“数据什么时候拉”这个联调真正的落点。一共四件事：为什么拆、往下传、往上通知、何时拉数据。

## 为什么要把页面拆成组件

把“搜索框 + 列表 + 空状态 + 加载态”全写在一个文件里，改一处搜索逻辑要在整页代码里定位，想把“任务卡片”复用到详情页只能复制粘贴。组件的价值就在于此：把职责切成小块，每块自带输入输出，能独立看、独立改、独立复用。

## Props：父传子

父组件通过 Props 把数据传给子组件，子组件拿到的是只读副本，自己不能改。这对应后端的“函数参数”：调用方传入，接收方只读。

```vue
<!-- 父组件：把 tasks 和 keyword 传给子组件 -->
<TaskList :tasks="tasks" :keyword="keyword" />

<!-- 子组件 TaskList.vue -->
<script setup>
defineProps({ tasks: Array, keyword: String })
</script>

<template>
  <li v-for="t in tasks" :key="t.id">{{ t.name }}</li>
</template>
```

数据只能从父往子流动，这就是单向数据流。子组件若想改数据，不能直接改 Props，得走下面的 Emits。

## Emits：子传父

子组件不该直接改父组件的状态，而是发一个事件“通知”父组件，由父组件决定怎么改。这对应后端的“回调”：子组件只上报，不越权。

```vue
<!-- 子组件 SearchInput.vue：发出 update 事件 -->
<script setup>
const emit = defineEmits(['update:keyword'])
function onInput(e) { emit('update:keyword', e.target.value) }
</script>

<template>
  <input :value="keyword" @input="onInput" />
</template>

<!-- 父组件：监听事件，自己改状态 -->
<SearchInput :keyword="keyword" @update:keyword="keyword = $event" />
```

`v-model` 就是上面这套“传值 + 监听 update”的语法糖：`<SearchInput v-model:keyword=“keyword” />` 一行顶两行。

## 插槽：留一个内容位

父组件想往子组件里塞一段自定义内容时，子组件留一个 `<slot>` 占位。默认插槽已经覆盖绝大多数场景，命名插槽和作用域插槽等用到时再查文档即可，这里不展开。

## 生命周期：数据什么时候拉

这是后端联调最该记住的一点。组件从“被创建”到“从页面消失”会经过几个阶段，最常用的两个钩子是：

```vue
<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'

const tasks = ref([])

onMounted(async () => {
  // 组件挂载到页面后执行一次，通常在这里拉后端数据
  tasks.value = await fetch('/api/tasks').then(r => r.json())
})

onBeforeUnmount(() => {
  // 组件从页面移除前执行，用来清理定时器、取消请求
})
</script>
```

记住 `onMounted` 就够了：**前端就是在组件挂载之后，通过 `onMounted` 里的 `fetch` 去调你的接口。** 这也是联调时判断“这行请求是页面一进来就发，还是点了按钮才发”的根据。

## 抽组件还是抽组合函数

一块逻辑该放哪，看它有没有界面：

| 场景 | 抽什么 | 例子 |
| --- | --- | --- |
| 有界面结构要复用 | 组件 | `TaskCard`、`EmptyState` |
| 无界面、纯逻辑要复用 | 组合函数 | `useTasks`、`usePolling` |
| 两者都有 | 组件包裹组合函数 | `TaskList` 里用 `useFilteredTasks` |

原则一句话：界面复用抽组件，逻辑复用抽组合函数，两者都要就把逻辑装进组件里的组合函数。

## 本节小结

- 组件是“带契约的部件”：按职责划边界，靠输入输出通信，能独立复用与演进。
- Props 向下只读传数据，Emits 向上发事件通知，一套单向数据流覆盖父子通信。
- `onMounted` 是前端向后端拉数据的标准时机，`onBeforeUnmount` 用来清理。
- 界面复用抽组件，逻辑复用抽组合函数，两者结合即“组件包裹组合函数”。

金句：组件把一页大代码拆成一盒零件，每个零件签好输入输出的契约，拼装和改动才不用再为一整页提心吊胆。