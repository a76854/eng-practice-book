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

上一节理清了分离之后前端的职责：把 JSON 渲染成页面，把状态变成视图。但数据一变、页面跟着变这件事，靠上一代**命令式地手写 DOM 操作**会越来越难维护。框架，正是被这个难题逼出来的。

> React 像一盒乐高基础板：只给你最稳的地基，房子怎么盖、用哪家的砖全由你挑；Vue 像宜家样板间：从一件家具到全屋定制都能递进，贴着直觉走；Angular 像精装交付的楼盘：户型、水电、物业规范一次配齐，开箱即住，但改格局的成本更高。三种选择没有优劣，只有约束与代价的不同。

本节不押宝任何框架，只想讲清一件事：站在后端视角，怎么读懂框架这个东西在解决什么、用什么代价解决。先立住那个所有框架共享的第一性原理，再逐个看三家对它的不同回答，最后给你一张可复盘、可解释的选型清单。

## 框架的诞生

在没有框架的年代，前端用 jQuery 命令式地改 DOM：用户输入一个字，就找到对应元素、改它的 `innerHTML`、顺手清理旧节点。一个任务列表过滤都写成一串 `document.getElementById(...)` 加手动拼接 HTML 的代码。当页面状态一多、交互一密，这套手工同步就成了谁也改不动的面条代码。

框架把这件事倒了过来：不再是命令式地改 DOM，而是声明式地描述状态与视图之间的映射，由框架在状态变化时自动重算映射、更新视图。所有框架共享的正是这一条第一性原理：

```text
UI = f(state)
```

把状态如何变成视图交给框架自动维护，开发者只需要声明两件事：界面长什么样、数据是什么。这正是理解 React 与 Vue 差异的钥匙：它们对这同一个函数，给了不同的实现。

## 同一需求，三种表达

以任务过滤输入框 + 列表为例，看三者在**视图表达**与**状态归属**上的差异。三段代码完成的是同一件事，差异在谁持有状态、谁决定何时重渲染、谁提供周边能力。

React 风格（JSX + 单向数据流 + 不可变更新）：

```javascript
// 示意：React 组件 TaskList.jsx（不可直接运行）
import { useState, useMemo } from 'react'

export default function TaskList({ tasks }) {
  const [keyword, setKeyword] = useState('')
  const filtered = useMemo(
    () => tasks.filter(t => t.filename.includes(keyword)),
    [tasks, keyword]
  )
  return (
    <>
      <input value={keyword} onChange={e => setKeyword(e.target.value)} />
      <ul>{filtered.map(t => <li key={t.id}>{t.filename} / {t.status}</li>)}</ul>
    </>
  )
}
```

Vue 风格（SFC 模板 + 响应式 + 可变更新）：

```javascript
// 示意：Vue 组件 App.vue（节选，不可直接运行）
import { ref, computed } from 'vue'

const keyword = ref('')
const tasks = ref([{ id: '1', filename: 'meeting.wav', status: 'done' }])
const filtered = computed(() => tasks.value.filter(t => t.filename.includes(keyword.value)))
// 模板：<input v-model="keyword" /> + <li v-for="t in filtered" :key="t.id">
```

Angular 风格（组件 + 服务 + 依赖注入 + RxJS 流）：

```javascript
// 示意：Angular 组件 task-list.component.ts（不可直接运行）
import { Component, inject } from '@angular/core'
import { TaskService } from './task.service'

@Component({
  selector: 'task-list',
  template: `
    <input [(ngModel)]="keyword" />
    <li *ngFor="let t of filtered()">{{ t.filename }} / {{ t.status }}</li>
  `
})
export class TaskListComponent {
  keyword = ''
  private tasks = inject(TaskService) // 由 DI 容器按作用域提供
  filtered() { return this.tasks.list().filter(t => t.filename.includes(this.keyword)) }
}
```

### 三种框架的区别

React 把可预测放在第一位：视图是状态的纯函数，数据单向流动，变化通过不可变更新显式触发。结构最薄、生态最宽，代价是心智门槛高，路由、状态库都要自己从生态里挑。

Vue 把渐进与直觉放在第一位：模板贴近 HTML，响应式自动追踪依赖，改数据即改视图对新手也符合直觉，还能从页面里一小块增强平滑演进到整站 SPA。代价是灵活性上不如 React 生态自由。

Angular 把企业级完备放在第一位：以平台视角提供官方的路由、表单、HTTP、依赖注入与 RxJS，强约定换来大型团队的长期一致。代价是概念多、上手陡、灵活度低。

| 维度 | React | Vue 3 | Angular |
| --- | --- | --- | --- |
| 视图表达 | JSX（JS 中写类 HTML） | SFC 模板（贴近原生 HTML） | 模板 + 指令（`*ngFor` 等） |
| 数据流 | 严格单向 | 默认单向，`v-model` 为语法糖 | 单向为主，RxJS 处理异步更原生 |
| 状态更新 | 不可变 + 显式触发 | 可变 + Proxy 自动追踪 | 可变或流 + 变更检测 |
| 组件通信 | props / callback / Context | props / emit / provide / Pinia | Input/Output / Service + DI |
| 官方周边 | 轻内核，路由状态靠社区 | 官方 Router / Pinia / Vite 插件 | 官方全家桶 |
| 学习曲线 | JS 心智要求高 | HTML 心智友好，渐进增强 | 概念多，上手陡 |

表格印证了那句判断：三家没有优劣，只有把什么放第一的取舍。理解它们，比记住语法更有用。

## 选型的五个客观维度

对后端背景的团队，选型不该是谁更流行的投票，而是一张可复盘的清单：

1. **团队熟悉度与招聘面**：React 生态岗位最多，Vue 在中文文档与上手速度上有优势，Angular 在金融、政企存量大。熟悉度直接决定联调成本。
2. **项目约束**：内容型官网（SEO 强）偏 SSR/SSG；后台管理系统（交互中等、表单多）三者皆可；需在既有服务端渲染页里只增强一块区域时，Vue 的渐进能力更贴合。
3. **规范诉求**：要强一致的目录、依赖与测试脚手架选 Angular；希望团队自定规范、按需引入选 React；介于二者之间选 Vue。
4. **生态与周边**：React 生态最宽但选型成本高，Vue 的官方链路更收敛，Angular 的官方方案最收敛但灵活性最低。
5. **长期维护**：关注三年后新人能否低成本接手。文档完整度、升级迁移成本，往往比语法喜好更重要。

一个交互中等、以后端 API 为核心的后台系统，选型上更看重后端开发者能快速读懂前端目录与契约、联调成本低。下一节不再比较框架，而是选定一个具体框架（Vue 3 + Vite）来讲清前端开发本身。

## 本节小结

- 框架是被手改 DOM的不可维护性逼出来的，它把命令式改 DOM升维成声明式描述状态到视图的映射。
- 所有框架共享 `UI = f(state)` 这条第一性原理，React、Vue、Angular 是对它三种不同的兑现。
- 三家各有取舍：React 用显式换可预测，Vue 用代理换直觉，Angular 用约定换一致。
- 选型是一张五维度清单（熟悉度、约束、规范、生态、长期维护）的权衡，而不是能力的排名。

框架是约束的集合，不是能力的榜单；读懂它把什么放在第一位，你才能在给定团队与项目约束下，给出可解释、可复盘的选型判断。