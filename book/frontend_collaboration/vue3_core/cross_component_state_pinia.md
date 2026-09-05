---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

# 跨组件共享的状态

学完本节，你能回答：

- 两个组件要共享同一份状态时，用 Props 逐层透传有什么问题？什么时候该提升到 Pinia？
- Pinia 的 State、Getter、Action 三层各自承担什么职责？
- 前端状态和后端状态是什么关系？为什么说“以后端为真相、前端为缓存”？

路由解决了页面之间的切换，但还剩一块拼图：有些状态要跨组件、跨页面共享。这一节讲共享状态归谁管、怎么变。

> Props 逐层透传像一层层递话，十个人传一份菜单，传到第十个人早走了样。Pinia 像挂在大厅的一块公告板：谁要看就抬头看一眼，谁要改就上板改，用不着经过中间任何一个人。

这一节讲三件事：什么时候该用全局状态、它内部的三层模型长什么样、它和后端状态是什么边界。只讲够用的部分，不往深处钻。

## 什么时候该用全局状态

两个页面都要同一份“任务列表”：列表页要渲染它，一个统计组件要读它算“已完成了几条”。若靠 Props 把这份数据从根组件一层层往下传，每加一层中间组件都要透传一遍，改一个字段要动一串文件。这种“跨组件、跨页面共享的可变状态”，就该提升到全局状态库里，谁用谁直接取。

## State、Getter、Action 三层

Pinia 是 Vue 3 官方推荐的状态库，一个小 store 就三层：

| 层 | 职责 | 后端类比 |
| --- | --- | --- |
| State | 原始可变状态 | 数据库里的数据 |
| Getter | 由 State 派生的只读值，带缓存 | 计算字段、查询方法 |
| Action | 变更 State 的唯一入口，可异步 | Service 方法 |

```javascript
// src/stores/tasks.ts
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export const useTasks = defineStore('tasks', () => {
  // State：原始状态
  const tasks = ref([])
  const keyword = ref('')
  const loading = ref(false)

  // Getter：派生值，带缓存
  const filtered = computed(() => tasks.value.filter(t => t.name.includes(keyword.value)))
  const doneCount = computed(() => tasks.value.filter(t => t.status === 'done').length)

  // Action：唯一的写入口
  async function load() {
    loading.value = true
    try {
      tasks.value = await fetch('/api/tasks').then(r => r.json())
    } finally {
      loading.value = false
    }
  }
  function setKeyword(v) { keyword.value = v }

  return { tasks, keyword, loading, filtered, doneCount, load, setKeyword }
})
```

用法上，任何组件 `const store = useTasks()` 拿到的都是同一个单例，谁改、谁读，看到的都是一份。这对应后端“任何 handler 都能拿到同一个服务实例”。

## 前端状态与后端状态的边界

这里有一条必须分清的边界：

| 维度 | 前端状态（Pinia） | 后端状态（数据库） |
| --- | --- | --- |
| 真相地位 | 缓存，刷新即失 | 持久真相 |
| 职责 | 交互态、过滤、分页 | 权威数据、一致性 |

原则一句话：**以后端为真相，前端为缓存。** 前端不管你缓存了啥，刷新页面、重新进入后，都以 `load()` 重新拉取后端为准。联调时“刷新后状态丢了”往往是正常的，除非这段状态本就应该持久化到后端。

## 本节小结

- 跨组件、跨页面共享的可变状态，别用 Props 一路透传，提升到 Pinia 全局状态。
- Store 分三层：State 存原始状态、Getter 存派生只读、Action 是唯一写入口，对应后端的数据、查询、Service。
- Pinia 是单例，任何组件拿到的都是同一份状态。
- 前端状态是缓存、后端状态是真相，刷新即以 `load()` 重拉为准。

金句：状态件归谁管是第一等要紧事，管错了地方，联调时“数据动了视图不动”“刷新了状态还在”这些怪相就会找上门。