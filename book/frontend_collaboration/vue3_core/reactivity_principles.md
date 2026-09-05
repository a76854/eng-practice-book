---
kernelspec:
  name: book-venv
  display_name: Python 3 (book)
---

# 数据如何驱动视图

学完本节，你能回答：

- 用浏览器原生方式让"数据一变、界面就变"，为什么又累又容易错？
- `ref` 和 `reactive` 解决了什么问题？为什么 `ref` 在 JavaScript 里要写 `.value`？
- `computed` 和 `watch` 的分工是什么？什么情况下用哪个？
- 看到一个页面，你能说出它的数据、派生值和副作用分别是什么吗？

前端概况一章说过，Vue 用声明式描述"状态到视图"的映射，靠响应式实现"改数据即改视图"。这一节不急着下定义，先看看没有响应式时这件事有多累，再看 Vue 怎么把它接过去。

> 你在表格里写下公式 `=A1+A2`，改 A1，结果格自己就重算了，不用手动刷新。响应式就是想让界面变成这样一张表：你只负责改数据，派生和刷新都自动发生。下面要讲的三件事——存数据、算派生、做副作用——都是在为这张表添零件。

这一节只讲三个最常用的接口：`ref`、`computed`、`watch`。它们的顺序不是随意的：先有数据（`ref`），才能有派生（`computed`），派生值变化时才谈得上副作用（`watch`）。顺着这条线走一遍，比背三个定义有用得多。

## 没有响应式之前，这活有多累

先用最朴素的方式做一个列表过滤：一个输入框，下面一个列表，输入什么，列表就只显示名字里含有它的项。

```javascript
// 原生写法：数据是数据，界面是界面，中间的同步全靠手动牵线
const tasks = [{ name: '买牛奶' }, { name: '写周报' }]
const input = document.querySelector('input')
const list = document.querySelector('#list')

function render(keyword) {
  const html = tasks
    .filter(t => t.name.includes(keyword))
    .map(t => `<li>${t.name}</li>`)
    .join('')
  list.innerHTML = html
}

input.addEventListener('input', (e) => render(e.target.value))
render('')
```

这十几行里真正有用的信息只有一条：`tasks` 和 `keyword` 会变。可是为了让界面跟得上，你得自己数着"有哪几次变化要同步"：初始要渲染一次、输入要渲染一次、以后增删数据还要各渲染一次。漏掉任何一次，界面就和数据对不上。数据在 A 处，界面在 B 处，中间那根"同步的线"要你亲手牵着，这就是所有前端框架要消灭的那份活。响应式的全部含义，就是把这条线交给框架。

## ref：让一个值变成"可观测"的

为什么普通变量不行？因为 `let keyword = 'x'` 这种赋值，JavaScript 本身就提供不了"被修改了就通知一声"的能力——你改了它，谁都收不到消息。于是 Vue 用 `ref` 把值装进一层"盒子"，你通过 `keyword.value` 读写，读写都经过这个盒子，Vue 才有机会"知道"你改了什么。

```javascript
import { ref } from 'vue'

const keyword = ref('')      // 一个可观测的盒子，初始为空

keyword.value = '周报'       // JavaScript 里读写都要 .value
console.log(keyword.value)   // 周报
```

这也就顺带回答了初学者最常问的问题：为什么模板里不用 `.value`、JavaScript 里却要？因为模板是 Vue 自己解析的，它认得 `ref` 这个盒子，会自动帮你拆开；而 JavaScript 代码是你写的，Vue 没法替你拆，你就得自己 `.value`。`.value` 不是多此一举，它是"读写要经过盒子"这件事在代码里留下的痕迹。

`ref` 装的是单值。要装对象和数组，有它的兄弟 `reactive`，它让对象和数组的每一层都可观测，改属性、`push` 都能被察觉。

```javascript
import { reactive } from 'vue'

const state = reactive({ tasks: [], loading: false })
state.tasks.push({ name: '买牛奶' })   // 直接改，视图跟得上
```

两者怎么选，一张表就够：

| | ref | reactive |
| --- | --- | --- |
| 装什么 | 单值：字符串、数字、布尔 | 对象、数组 |
| 怎么读写 | JavaScript 里 `.value`，模板里不用 | 直接 `.属性` |
| 什么时候用 | 输入框、开关、计数 | 一组彼此相关的状态 |

## computed：把"算出来的值"声明出来

现在有了 `keyword`，你还缺一个"过滤后的列表"才能填进页面。你当然可以每次用到时现算：

```javascript
const filtered = tasks.value.filter(t => t.name.includes(keyword.value))
```

这么写能跑，但有两个毛病：一是每次界面更新都要重新过滤一遍，哪怕 `keyword` 根本没变；二是"过滤"这段逻辑散落在模板和代码各处，改起来要到处翻。`computed` 就是冲这两点来的：它把"由谁算出"声明一次，框架替你缓存，依赖没变就不重算。

```javascript
import { ref, computed } from 'vue'

const keyword = ref('')
const tasks = ref([{ name: '买牛奶' }, { name: '写周报' }])

// 声明一个派生值：由 tasks 和 keyword 推出，依赖不变就复用上次结果
const filtered = computed(() => tasks.value.filter(t => t.name.includes(keyword.value)))
```

`computed` 对应的后端心智是"物化视图"：底层数据变了，这个"视图"自动刷新；没人动底层数据时，它把上次算好的结果直接还给你，不重算。巧合的是，后端查库也有一样的设计——常用查询建个物化视图，省的每次重算。

## watch：给变化挂一个"反应"

`computed` 管的是"算出一个值"，但有些事不是算值能解决的：关键词一变，你要发个请求、记条日志、往本地存一笔。这些"值变了就要去做"的动作，归 `watch` 管。

```javascript
import { ref, watch } from 'vue'

const keyword = ref('')

// keyword 一变，就执行这段副作用
watch(keyword, (nv, ov) => {
  console.log(`关键词变了：${ov} -> ${nv}`)
  // 通常在这里把新关键词发给后端，重新拉列表
})
```

至此，四个接口的分工可以一句话钉死：

| | 管什么 | 一句话 |
| --- | --- | --- |
| ref / reactive | 存数据 | 可观测的容器 |
| computed | 算派生 | 由别的值推出、带缓存 |
| watch | 做副作用 | 值变了顺手做点事 |

用后端的话再翻译一遍：`ref`/`reactive` 是存储字段，`computed` 是派生查询，`watch` 是变更时触发的回调。存、算、响，这条线讲完，Vue 里"数据怎么动起来"就通了。

## 一个容易踩的坑

两个新手最常见的报错，都来自对"盒子"理解不牢：一是 JavaScript 里漏写 `.value`，把盒子当成了值本身；二是把 `reactive` 对象解构了（`const { tasks } = state`），一旦拆开就断了响应。规避的办法很简单：简单值统一用 `ref`，别为了少敲一个 `.value` 把自己绕进去。

## 本节小结

- 响应式解决的是"数据变了界面要手动改"这件苦差：原来中间那根同步的线要你亲手牵，现在交给框架。
- `ref` 装单值、`reactive` 装对象，都是"可观测的盒子"，这正是 JavaScript 里要 `.value` 的由来。
- `computed` 声明派生值、带缓存；`watch` 挂载副作用、变则执行。先存、再算、后响，顺序不是随意的。
- 读一段 Vue 代码，先找数据（`ref`/`reactive`），再找派生（`computed`），最后找副作用（`watch`），三样齐了就懂了。

金句：响应式不是魔法，它只是把"数据一变界面就变"这件本该由人盯着的苦差，变成了框架替你盯着的默认行为。