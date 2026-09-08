---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

# 框架三驾马车

学完本节，你能回答：

- 前端框架要解决的第一性原理问题是什么？为什么说它是把状态可靠地变成视图？
- React、Vue、Angular 各自把什么放在第一位？各自换来什么、牺牲什么？
- 三者在视图表达、数据流与工程约束上的 trade-off 是什么？
- 面对一个后端背景、交互中等的后台系统，你会用哪些客观维度做选型判断？

上一节理清了分离之后前端的职责：把 JSON 渲染成页面，把状态变成视图。但数据一变、页面跟着变这件事，靠上一代命令式地手写 DOM 操作会越来越难维护。框架，正是被这个难题逼出来的。

> 建房子有三种做法。React 是一套结构标准——只规定梁柱怎么接，墙用什么材料、水电怎么走、家具怎么摆全由施工队自己定；Vue 是渐进式精装方案——从一面墙的改造到整栋楼的交付，每一步都贴着需求走，不会让你一上来就做全部决定；Angular 是开发商的一站式交钥匙工程——户型、水电、物业规范一次配齐，拎包入住，但改格局的代价更高。

本节站在后端视角，怎么读懂框架这个东西在解决什么、用什么代价解决。先立住那个所有框架共享的第一性原理，再逐一看三家对它的不同回答。

## 框架的诞生

在没有框架的年代，前端用 jQuery 命令式地改 DOM：用户输入一个字，就找到对应元素、改它的 `innerHTML`、顺手清理旧节点。一个任务列表过滤都写成一串 `document.getElementById(...)` 加手动拼接 HTML 的代码。

当页面状态一多、交互一密，这套手工同步就成了谁也改不动的面条代码。问题出在“命令式”这件事本身：你要把“数据变了”翻译成“哪个 DOM 节点该改成什么”，这层翻译工作量和代码行数跟页面规模成正比，而页面规模每翻一倍，翻译的复杂度要翻四倍。

框架把这件事倒了过来。不再是命令式地改 DOM，而是声明式地描述状态与视图之间的映射，由框架在状态变化时自动重算映射、更新视图。所有框架共享的正是这一条第一性原理：

```text
UI = f(state)
```

把状态如何变成视图交给框架自动维护，开发者只需要声明两件事：界面长什么样、数据是什么。这正是理解 React 与 Vue 差异的钥匙：它们对这同一个函数，给了不同的实现。

## 同一需求，三种表达

下面用一个文档搜索举一个例子，看看三种框架的实现。页面包括一个搜索框、一个搜索按钮、加载状态、结果列表展示、错误提示。同一个需求，看三个框架各怎么写。

### React 风格：显式触发、不可变更新

React 把“可预测”放在第一位。数据单向流动，状态变化通过不可变更新显式触发。开发者明确知道“什么时候变了、变成什么了”。

```javascript
// React 组件 DocSearch.jsx
import { useState } from 'react'

export default function DocSearch() {
  const [query, setQuery] = useState('')
  const [results, setResults] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const search = async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await fetch(`/api/search?q=${query}`)
      if (!res.ok) throw new Error('请求失败')
      setResults(await res.json())
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div>
      <input value={query} onChange={(e) => setQuery(e.target.value)} />
      <button onClick={search}>搜索</button>
      {loading && <p>加载中...</p>}
      {error && <p style={{ color: 'red' }}>错误：{error}</p>}
      <ul>
        {results.map(r => (
          <li key={r.url}><a href={r.url}>{r.title}</a></li>
        ))}
      </ul>
    </div>
  )
}
```

关键特征都在代码里：
- 状态用 `useState` 声明，每一块状态独立
- 状态更新用 `setXxx(newValue)` 显式触发，旧值和新值是完全不同的两个对象
- 副作用（数据请求）在点击事件里显式触发
- 视图是状态的纯函数：给定一套 `query`、`results`、`loading`、`error`，渲染结果完全确定

React 的风格可以概括为：**一切变化都是显式的，一切渲染都是可预测的。** 代价是开发者要写更多代码——状态管理、显式更新，每一步都要手动处理。

### Vue 风格：响应式代理、自动追踪

Vue 把“渐进与直觉”放在第一位。模板贴近 HTML，响应式系统用 Proxy 自动追踪依赖，改数据即改视图。

```vue
<!-- Vue 组件 DocSearch.vue -->
<script setup>
import { ref } from 'vue'

const query = ref('')
const results = ref([])
const loading = ref(false)
const error = ref(null)

const search = async () => {
  loading.value = true
  error.value = null
  try {
    const res = await fetch(`/api/search?q=${query.value}`)
    if (!res.ok) throw new Error('请求失败')
    results.value = await res.json()
  } catch (err) {
    error.value = err.message
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <div>
    <input v-model="query" />
    <button @click="search">搜索</button>
    <p v-if="loading">加载中...</p>
    <p v-if="error" style="color: red">错误：{{ error }}</p>
    <ul>
      <li v-for="r in results" :key="r.url">
        <a :href="r.url">{{ r.title }}</a>
      </li>
    </ul>
  </div>
</template>
```

关键特征：
- `ref()` 把普通值变成响应式代理，改 `query.value` 时所有依赖这个值的地方自动更新
- `v-model` 是双向绑定语法糖：输入框的变化自动写回 `query.value`
- `@click` 把点击事件绑定到 `search` 方法
- 模板用 `v-if` 控制显示、`v-for` 渲染结果列表、`{{ }}` 插入值

Vue 的风格可以概括为：**想改就改，框架帮你追踪变化。** 代码更接近原生 HTML，心智负担小，新手也能快速上手。代价是响应式系统有一定黑盒性质，异步场景下要额外注意引用稳定性。

### Angular 风格：依赖注入、响应式流

Angular 以“企业级完备”为出发点。官方提供路由、表单、HTTP、依赖注入的全套方案，通过 RxJS 流式管理异步数据。

```typescript
// Angular 组件 doc-search.component.ts
import { Component, inject, signal } from '@angular/core'
import { HttpClient } from '@angular/common/http'

@Component({
  selector: 'doc-search',
  template: `
    <div>
      <input (input)="onInput($event)" [value]="query()" />
      <button (click)="search()">搜索</button>
      @if (loading()) { <p>加载中...</p> }
      @if (error()) { <p style="color: red">错误：{{ error() }}</p> }
      <ul>
        @for (r of results(); track r.url) {
          <li><a [href]="r.url">{{ r.title }}</a></li>
        }
      </ul>
    </div>
  `
})
export class DocSearchComponent {
  private http = inject(HttpClient)

  query = signal('')
  results = signal<any[]>([])
  loading = signal(false)
  error = signal<string | null>(null)

  onInput(event: Event) {
    this.query.set((event.target as HTMLInputElement).value)
  }

  search() {
    this.loading.set(true)
    this.error.set(null)
    this.http.get<any[]>(`/api/search?q=${this.query()}`).subscribe({
      next: (data) => { this.results.set(data); this.loading.set(false) },
      error: (err) => { this.error.set(err.message); this.loading.set(false) },
    })
  }
}
```

Angular 的风格可以概括为：**框架替你管好一切，你只需要填业务逻辑。** 依赖注入、HttpClient 的观察者流、信号响应式三者配合，形成一套完整的异步数据管理方案。代价是概念多、写法重、学习曲线陡。

### 三种框架的差异

同一个文档搜索需求，三种框架的写法迥异。差异的根源不在语法，而在它们对“状态怎么变、视图怎么跟着变”这件事给出了不同的答案。

| 维度 | React | Vue 3 | Angular |
| --- | --- | --- | --- |
| 视图表达 | JSX | SFC 模板 + `v-` 指令 | 模板 + `@` / `*` 指令 |
| 状态更新 | 不可变 + 显式触发 | 可变 + Proxy 自动追踪 | 可变 + Signal / RxJS 流 |
| 副作用管理 | `useEffect` 手动声明依赖 | `watch` / `watchEffect` | RxJS 管道 + `effect` |
| 异步处理 | 开发者自行管理 | 开发者自行管理 | RxJS 原生流式管理 |
| 数据流方向 | 严格单向 | 默认单向，`v-model` 是语法糖 | 单向为主，RxJS 流贯穿 |
| 依赖注入 | 无内置（需 Context 或第三方） | 无内置（Provide / Inject 可用） | 内置 DI，贯穿全框架 |
| 官方生态 | 轻内核，路由/状态靠社区选型 | 官方 Router / Pinia / Vite 插件 | 官方全家桶，一步到位 |
| 学习曲线 | JS 心智要求高 | HTML 友好，渐进增强 | 概念多，上手最陡 |

### 为什么会有这些差异

React 选择“显式”，因为它把可维护性放在第一位。当代码规模膨胀到成千上万个组件时，显式的数据流让你能追踪每一处变化。代价是写一个简单功能也要写不少代码。

Vue 选择“自动”，因为它把上手体验放在第一位。后端开发者转前端，最怕的就是“不知道东西为什么会变”，Vue 的响应式让你可以像改普通变量一样改数据，心智负担最低。代价是自动追踪在某些边缘场景下会失效，需要额外处理。

Angular 选择“完备”，因为它把长期维护放在第一位。依赖注入、RxJS、内置工具链——这些设计都指向一个目标：一个大型团队在五年后还能正常接手。代价是前期投入最高，改别人的代码最不灵活。

三家都在解决同一个问题：如何让状态可靠地变成视图。只是它们押注在不同的解法上。

## 选型的五个客观维度

对后端背景的团队，选型不该是谁更流行的投票，而是一张可复盘的清单：

**1. 团队熟悉度与招聘面**

React 生态岗位最多，英文文档和社区讨论最丰富，招聘面最宽。Vue 在中文文档与上手速度上有明显优势，后端转前端的同事在 Vue 上更容易快速产出。Angular 在金融、政企等大型组织里存量最大，招聘面较窄，但维护人员的长期稳定性更高。

**2. 项目约束**

内容型官网（SEO 强依赖）偏 SSR / SSG，三框架都有对应方案，但实现成本不同。后台管理系统（交互中等、表单多）三者皆可。如果项目要求“在既有服务端渲染页里只增强一块区域”，Vue 的渐进能力最贴合，React 也能做但配置更重，Angular 基本不适用。

**3. 规范诉求**

希望团队按官方规范走、不用争论目录结构和测试方案的，选 Angular。希望团队自定规范、按需引入、保留最大灵活度的，选 React。介于二者之间的，选 Vue——官方链路比 React 更收敛、比 Angular 更灵活。

**4. 生态与周边**

React 生态最宽但选型成本高（你要从几十种路由方案里挑一个），Vue 的官方链路更收敛，Angular 的官方方案最收敛但灵活性最低。选型成本从低到高依次是 Angular < Vue < React，灵活性则反过来。

**5. 长期维护**

关注三年后新人能否低成本接手。文档完整度、升级迁移成本，往往比语法喜好更重要。React 和 Vue 的升级策略相对温和，Angular 的大版本升级在早期有过较大的迁移成本，近几个版本已经平稳很多，但仍是需要考量的因素。

| 维度 | React | Vue | Angular |
| --- | --- | --- | --- |
| 选型成本 | 高（方案自搭） | 中等（官方方案+社区选型） | 低（官方全套） |
| 上手速度 | 中等（需理解 JSX/不可变） | 快（模板贴近 HTML） | 慢（概念多） |
| 灵活度 | 高 | 中等 | 低 |
| 团队规模适配 | 不限 | 不限 | 大型团队最有优势 |

一个交互中等、以后端 API 为核心的后台系统，选型上更看重后端开发者能快速读懂前端目录与契约、联调成本低。三个框架都能胜任这个场景，但 Vue 的上手曲线最低，React 的生态最宽，Angular 的规范最严。


## 本节小结

- 框架是被手改 DOM 的不可维护性逼出来的，它把命令式改 DOM 升维成声明式描述状态到视图的映射。
- 所有框架共享 `UI = f(state)` 这条第一性原理，React、Vue、Angular 是对它三种不同的兑现。
- React 用显式换可预测，Vue 用自动追踪换直觉，Angular 用全家桶换长期一致。三家没有优劣，只有把什么放第一的取舍。
- 选型是一张五维度清单（熟悉度、约束、规范、生态、长期维护）的权衡，而不是能力的排名。后端背景团队选型，上手成本与联调效率往往比生态宽度更重要。